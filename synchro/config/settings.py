from pydantic import BaseModel


class SettingsLimitSchema(BaseModel):
    run_time_seconds: int = 0


class SettingsSchema(BaseModel):
    limits: SettingsLimitSchema = SettingsLimitSchema()
