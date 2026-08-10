import aiohttp
import logging
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

class SMMPanelClient:
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.api_key = api_key

    async def place_order(self, service_id: int, link: str, quantity: int) -> Tuple[bool, Dict[str, Any]]:
        """
        Sends order request to SMM panel API v2
        """
        params = {
            "key": self.api_key,
            "action": "add",
            "service": service_id,
            "link": link,
            "quantity": quantity
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                # SMM Panel APIs usually support standard Form POST or GET requests
                async with session.post(self.api_url, data=params, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        if isinstance(data, dict):
                            if "order" in data:
                                return True, data
                            elif "error" in data:
                                return False, {"error": data.get("error")}
                        return False, {"error": f"Invalid JSON response: {data}"}
                    else:
                        text = await resp.text()
                        return False, {"error": f"HTTP {resp.status}: {text[:100]}"}
        except Exception as e:
            logger.error(f"SMM API Request Error: {e}")
            return False, {"error": str(e)}

    async def get_balance(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Retrieves current balance from SMM Panel API v2
        """
        params = {
            "key": self.api_key,
            "action": "balance"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, data=params, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        if isinstance(data, dict) and "balance" in data:
                            return True, data
                        elif isinstance(data, dict) and "error" in data:
                            return False, {"error": data.get("error")}
                        return False, {"error": f"Invalid response: {data}"}
                    else:
                        text = await resp.text()
                        return False, {"error": f"HTTP {resp.status}: {text[:100]}"}
        except Exception as e:
            logger.error(f"SMM API Balance Error: {e}")
            return False, {"error": str(e)}

    async def get_order_status(self, smm_order_id: int) -> Tuple[bool, Dict[str, Any]]:
        """
        Checks status of an existing SMM order
        """
        params = {
            "key": self.api_key,
            "action": "status",
            "order": smm_order_id
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, data=params, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        return True, data
                    else:
                        text = await resp.text()
                        return False, {"error": f"HTTP {resp.status}: {text[:100]}"}
        except Exception as e:
            logger.error(f"SMM API Status Error: {e}")
            return False, {"error": str(e)}
