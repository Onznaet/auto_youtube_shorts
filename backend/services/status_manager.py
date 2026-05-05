current_status = "Ожидание задач..."
current_model = ""
current_voice_engine = ""

def set_status(message: str):
    global current_status
    current_status = message
    print(f"[STATUS] {message}")

def get_status() -> str:
    global current_status
    return current_status

def set_current_model(model: str):
    global current_model
    current_model = model

def get_current_model() -> str:
    global current_model
    return current_model

def set_current_voice_engine(engine: str):
    global current_voice_engine
    current_voice_engine = engine

def get_current_voice_engine() -> str:
    global current_voice_engine
    return current_voice_engine
