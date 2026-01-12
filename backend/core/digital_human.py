import json
import os
import time
from typing import Optional, Dict, Any
from volcengine.visual.VisualService import VisualService

class DigitalHumanGenerator:
    def __init__(self):
        self.ak = os.getenv("VOLC_ACCESS_KEY")
        self.sk = os.getenv("VOLC_SECRET_KEY")
        self.service = VisualService()
        
        # Configure service
        if self.ak and self.sk:
            self.service.set_ak(self.ak)
            self.service.set_sk(self.sk)
        
        # Region config (fixed as per docs)
        self.service.set_host('visual.volcengineapi.com')
        # self.service.set_region('cn-north-1')

    def submit_task(self, image_url: str, audio_url: str, prompt: str = None, 
                    seed: int = -1, resolution: int = 1080, fast_mode: bool = False) -> Dict[str, Any]:
        """
        Submit a task to generate a digital human video.
        Docs: OmniHuman 1.5
        """
        if not self.ak or not self.sk:
            return {"error": "Missing Volcengine Credentials (VOLC_ACCESS_KEY, VOLC_SECRET_KEY)"}

        # req_key fixed as per docs
        req_key = "jimeng_realman_avatar_picture_omni_v15"
        
        body = {
            "req_key": req_key,
            "image_url": image_url,
            "audio_url": audio_url,
            "seed": seed,
            "output_resolution": resolution,
            "pe_fast_mode": fast_mode
        }
        
        if prompt:
            body["prompt"] = prompt

        try:
            # VisualService handles signing. 
            # We use the generic 'cv_submit_task' or just 'json_request' if available.
            # Looking at generic Volcengine SDK usage:
            # params = dict()
            # resp = self.service.cv_submit_task(params, body)
            # However, cv_submit_task might not be exposed directly in all versions.
            # Let's try to use the generic method if possible, or assume cv_submit_task exists.
            # Based on standard Volcengine SDK 'VisualService', it usually has specific methods.
            # If not, we might need to use `post` with signed auth.
            # But `VisualService` inherits from `Service`, which has `json` method.
            
            # Action=CVSubmitTask
            params = {
                "Action": "CVSubmitTask",
                "Version": "2022-08-31"
            }
            
            # Use the SDK's internal mechanism to send request
            # Usually: service.get_response(action, params, body) or service.json(action, params, body)
            # Let's try using the `cv_submit_task` if it's dynamic, otherwise use `json`.
            # A safer bet with the raw SDK is often:
            resp = self.service.json("CVSubmitTask", params, json.dumps(body))
            
            # Parse response
            # resp is usually a requests.Response object or a dict depending on SDK version?
            # In volcengine-python-sdk, .json() returns the parsed dict usually? 
            # No, `service.json` usually returns the raw response object? 
            # Let's check typical usage. `visual_service.potrait_effect(body)`...
            # Since this is a NEW feature (OmniHuman), it might not have a wrapper method.
            # We will use the generic call.
            
            if isinstance(resp, str):
                resp = json.loads(resp)
            elif hasattr(resp, 'json'):
                resp = resp.json()
            
            return resp

        except Exception as e:
            print(f"Volcengine Submit Error: {e}")
            return {"error": str(e)}

    def get_task_result(self, task_id: str) -> Dict[str, Any]:
        """
        Query task result.
        """
        if not self.ak or not self.sk:
            return {"error": "Missing Credentials"}

        req_key = "jimeng_realman_avatar_picture_omni_v15"
        
        body = {
            "req_key": req_key,
            "task_id": task_id
        }
        
        params = {
            "Action": "CVGetResult",
            "Version": "2022-08-31"
        }
        
        try:
            resp = self.service.json("CVGetResult", params, json.dumps(body))
            
            if isinstance(resp, str):
                resp = json.loads(resp)
            elif hasattr(resp, 'json'):
                resp = resp.json()
                
            return resp
        except Exception as e:
            return {"error": str(e)}
