import json
from typing import Dict, List, Tuple

class Relay:
    def __init__(self):
        self.name = ""
        self.storage = None
    
    def name(self) -> str:
        return self.name
    
    def init(self) -> None:
        pass
    
    def on_initialized(self, server: "Server") -> None:
        pass
    
    def accept_event(self, event: Dict) -> bool:
        pass
    
    def storage(self) -> "Storage":
        return self.storage
    
class Injector:
    def inject_events(self) -> "channel":
        pass
    
class Informationer:
    def get_nip11_information_document(self) -> Dict:
        pass
    
class CustomWebSocketHandler:
    def handle_unknown_type(self, ws: "WebSocket", typ: str, request: List[str]) -> None:
        pass
    
class ShutdownAware:
    def on_shutdown(self, context: dict) -> None:
        pass
    
class Logger:
    def infof(self, format: str, v: any) -> None:
        pass
    
    def warningf(self, format: str, v: any) -> None:
        pass
    
    def errorf(self, format: str, v: any) -> None:
        pass
    
class Storage:
    def init(self) -> None:
        pass
    
    def query_events(self, filter: Dict) -> Tuple[List[Dict], None]:
        pass
    
    def delete_event(self, id: str, pubkey: str) -> None:
        pass
    
    def save_event(self, event: Dict) -> None:
        pass
    
class AdvancedQuerier:
    def before_query(self, filter: Dict) -> None:
        pass
    
    def after_query(self, events: List[Dict], filter: Dict) -> None:
        pass
    
class AdvancedDeleter:
    def before_delete(self, id: str, pubkey: str) -> None:
        pass
    
    def after_delete(self, id: str, pubkey: str) -> None:
        pass
    
class AdvancedSaver:
    def before_save(self, event: Dict) -> None:
