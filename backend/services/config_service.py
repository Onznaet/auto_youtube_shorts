from sqlalchemy.orm import Session
import models

class ConfigService:
    def __init__(self, db: Session, project_id: int = None):
        self.db = db
        self.project_id = project_id
        
    def get(self, key: str, default: any = None) -> str:
        """
        Retrieves a setting by key. 
        First checks project-specific setting, then falls back to global setting.
        """
        # 1. Try project-specific setting
        if self.project_id is not None:
            setting = self.db.query(models.GlobalSettings).filter(
                models.GlobalSettings.project_id == self.project_id,
                models.GlobalSettings.key == key
            ).first()
            if setting and setting.value is not None and str(setting.value).strip() != "":
                return setting.value
                
        # 2. Try global setting
        setting = self.db.query(models.GlobalSettings).filter(
            models.GlobalSettings.project_id == None,
            models.GlobalSettings.key == key
        ).first()
        if setting and setting.value is not None and str(setting.value).strip() != "":
            return setting.value
            
        # 3. Fallback to default
        return default
        
    def get_bool(self, key: str, default: bool = False) -> bool:
        val = self.get(key)
        if val is None:
            return default
        return str(val).lower() == "true"
        
    def get_int(self, key: str, default: int = 0) -> int:
        val = self.get(key)
        if val is None:
            return default
        try:
            return int(val)
        except ValueError:
            return default
            
    def get_float(self, key: str, default: float = 0.0) -> float:
        val = self.get(key)
        if val is None:
            return default
        try:
            return float(val)
        except ValueError:
            return default
