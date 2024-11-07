from __future__ import annotations

import json
import random
import logging
from aiohttp import ClientSession, ClientError
from typing import List

from ..typing import AsyncResult, Messages
from .base_provider import AsyncGeneratorProvider, ProviderModelMixin
from ..image import ImageResponse

class AIUncensored(AsyncGeneratorProvider, ProviderModelMixin):
    url = "https://www.aiuncensored.info/ai_uncensored"
    api_endpoints_text = [
        "https://twitterclone-i0wr.onrender.com/api/chat",
        "https://twitterclone-4e8t.onrender.com/api/chat",
        "https://twitterclone-8wd1.onrender.com/api/chat",
    ]
    api_endpoints_image = [
        "https://twitterclone-4e8t.onrender.com/api/image",
        "https://twitterclone-i0wr.onrender.com/api/image",
        "https://twitterclone-8wd1.onrender.com/api/image",
    ]
    working = True
    supports_stream = True
    supports_system_message = True
    supports_message_history = True
    
    default_model = 'TextGenerations'
    text_models = [default_model]
    image_models = ['ImageGenerations']
    models = [*text_models, *image_models]
    
    model_aliases = {
        "flux": "ImageGenerations",
    }

    @staticmethod
    def generate_cipher() -> str:
        return ''.join([str(random.randint(0, 9)) for _ in range(16)])

    @staticmethod
    async def try_request(session: ClientSession, endpoints: List[str], data: dict, proxy: str = None):
        available_endpoints = endpoints.copy()
        random.shuffle(available_endpoints)
        
        while available_endpoints:
            endpoint = available_endpoints.pop()
            try:
                async with session.post(endpoint, json=data, proxy=proxy) as response:
                    response.raise_for_status()
                    return response
            except ClientError as e:
                logging.warning(f"Failed to connect to {endpoint}: {str(e)}")
                if not available_endpoints:
                    raise
                continue
        
        raise Exception("All endpoints are unavailable")

    @classmethod
    def get_model(cls, model: str) -> str:
        if model in cls.models:
            return model
        elif model in cls.model_aliases:
            return cls.model_aliases[model]
        else:
            return cls.default_model

    @classmethod
    async def create_async_generator(
        cls,
        model: str,
        messages: Messages,
        proxy: str = None,
        **kwargs
    ) -> AsyncResult:
        model = cls.get_model(model)
        
        headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'cache-control': 'no-cache',
            'content-type': 'application/json',
            'origin': 'https://www.aiuncensored.info',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': 'https://www.aiuncensored.info/',
            'sec-ch-ua': '"Not?A_Brand";v="99", "Chromium";v="130"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Linux"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'cross-site',
            'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
        }
        
        async with ClientSession(headers=headers) as session:
            if model in cls.image_models:
                prompt = messages[-1]['content']
                data = {
                    "prompt": prompt,
                    "cipher": cls.generate_cipher()
                }
                response = await cls.try_request(session, cls.api_endpoints_image, data, proxy)
                response_data = await response.json()
                image_url = response_data['image_url']
                image_response = ImageResponse(images=image_url, alt=prompt)
                yield image_response
                
            elif model in cls.text_models:
                data = {
                    "messages": messages,
                    "cipher": cls.generate_cipher()
                }
                response = await cls.try_request(session, cls.api_endpoints_text, data, proxy)
                async for line in response.content:
                    line = line.decode('utf-8')
                    if line.startswith("data: "):
                        try:
                            json_str = line[6:]
                            if json_str != "[DONE]":
                                data = json.loads(json_str)
                                if "data" in data:
                                    yield data["data"]
                        except json.JSONDecodeError:
                            continue
