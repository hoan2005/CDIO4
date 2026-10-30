
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Các biến cấu hình với kiểu dữ liệu cụ thể
    PROJECT_NAME: str
    PORT: int 
    
    # Cấu hình bảo mật
 

    # Chỉ định file .env để đọc
    model_config = SettingsConfigDict(env_file=r"\backend\.env", extra="ignore")

# Khởi tạo đối tượng settings để dùng chung cho toàn dự án
settings = Settings()

