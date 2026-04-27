from backend.services.processing_service import ProcessingService
from backend.services.state_service import StateService
from backend.services.ws_service import WsHub

state_service = StateService()
state_service.load()
ws_hub = WsHub()
processing_service = ProcessingService(state_service, ws_hub)
