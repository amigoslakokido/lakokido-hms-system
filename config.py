import os
BASE_DIR = os.path.dirname(__file__)

class Config:
    SECRET_KEY = "HMS_PRO_KEY"
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "hms_smart.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    LANG_DIR = os.path.join(BASE_DIR, "langs")
