import os
import time
import pprint
import json

import requests

from typing import BinaryIO, Optional, Any, List

from .utils import get_logger

_logger = get_logger()


def _make_openai_request(api_path: str, request_data: Any, request_json: Any, request_files: dict,
                         max_retries: int = 0, timeout: float = 60.) -> Any:
    if os.path.exists(".env"):
        try:
            import dotenv
            dotenv.load_dotenv()
        except ImportError:
            _logger.warning(".env found but dotenv not installed. Please install python-dotenv to use .env file.")

    api_endpoint = os.environ.get("OPENAI_API_BASE")
    if api_endpoint is None:
        api_endpoint = "https://api.openai.com/v1"

    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key is None:
        raise RuntimeError("OPENAI_API_KEY environment variable not set")

    # proxies = {
    #     "http": "http://azureuser:%Jy44czQ8p6HI2Ao@23.97.70.12:3128",
    #     "https": "http://azureuser:%Jy44czQ8p6HI2Ao@23.97.70.12:3128",
    # }

    num_retries = 0
    delay = 1.
    while True:
        try:
            response = requests.post(
                api_endpoint + api_path,
                data=request_data,
                json=request_json,
                files=request_files,
                headers={
                    "Authorization": "Bearer " + api_key,
                },
                timeout=timeout,
                # proxies=proxies,
            )
            if response.status_code != 200:
                raise RuntimeError(f"Error when making OpenAI request: {response.text}")

            return response.text
        except KeyboardInterrupt:
            raise
        except:
            num_retries += 1
            if num_retries > max_retries:
                _logger.exception(f"Maximum number of retries (%d) exceeded.", max_retries)
                raise

            delay *= 2
            _logger.exception('Request failed. Retry in %f seconds.', delay)
            time.sleep(delay)

            # Reset file IO.
            for file in request_files.values():
                file.seek(0)


def openai_audio(audio_file: BinaryIO, prompt: str,
                 mode: str = "translations", language: Optional[str] = None,
                 response_format: str = "srt",
                 timeout: float = 60., max_retries: int = 0) -> str:
    """Translate / transcribe audio to text.

    Args:
        audio_file (BinaryIO): The audio file to translate / transcribe.
        prompt (str): The prompt to use for translation.
        mode (str, optional): The mode of the request. Defaults to "translations". Can be "transcriptions".
        language (str, optional): The language of the transcription. Defaults to None. Only useful when mode is "transcriptions".
        response_format (str, optional): The format of the response. Defaults to "srt".
        timeout (float): The timeout for the request.
        max_retries (int): The maximum number of retries.

    Returns:
        str: The translated text.
    """
    if mode not in ["translations", "transcriptions"]:
        raise ValueError(f"Invalid mode: {mode}, should be one of 'translations', 'transcriptions'")

    model = "whisper-1"
    request_params = {
        "model": model,
        "prompt": prompt,
        "response_format": response_format
    }

    if language is not None:
        request_params["lang"] = language

    return _make_openai_request("/audio/" + mode, request_params, {}, {"file": audio_file}, max_retries, timeout)


def openai_chat(messages: List[dict], timeout: float = 60., max_retries: int = 0) -> str:
    """Chat with the OpenAI API.

    Args:
        messages (List[dict]): The messages to send to the API.
        timeout (float): The timeout for the request.
        max_retries (int): The maximum number of retries.

    Returns:
        str: The response from the API.
    """
    params = {
        "model": "gpt-3.5-turbo",
        "temperature": 0.5,
        "messages": messages,
    }
    response = _make_openai_request("/chat/completions", {}, params, {}, max_retries, timeout)
    response = json.loads(response)
    _logger.debug("Chat response:\n%s", pprint.pformat(response))
    return response["choices"][0]["message"]["content"]
