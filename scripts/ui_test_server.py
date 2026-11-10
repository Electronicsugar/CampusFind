"""Isolated browser acceptance server; never connects to the application database.

python -m scripts.ui_test_server
Uses a fresh UUID directory under .local/ui-tests, SQLite test mode and real APIs/models.
"""
import json
from pathlib import Path
import uuid
from alembic.config import Config
from alembic import command
from backend.settings import Settings, ROOT


def main():
    directory=ROOT/'.local'/'ui-tests'/uuid.uuid4().hex
    directory.mkdir(parents=True,exist_ok=False)
    settings=Settings(database_url='sqlite:///'+str(directory/'test.db'),storage=directory/'photos',
                      origin='http://localhost:8017',testing=True,background_matching=True)
    config=Config('alembic.ini');config.set_main_option('sqlalchemy.url',settings.database_url)
    command.upgrade(config,'head')
    # Only this isolated process substitutes configuration before app import.
    Settings.from_env=classmethod(lambda cls:settings)
    from backend.main import app
    (ROOT/'.local'/'phase7-test-instance.json').write_text(json.dumps({'directory':str(directory),'url':settings.origin}))
    from PIL import Image,ImageDraw
    for n in range(2):
        image=Image.new('RGB',(480,640),'#e9eee7');draw=ImageDraw.Draw(image)
        draw.rounded_rectangle((145+n*10,110,335+n*10,540),radius=45,fill='#226954',outline='#113c31',width=6)
        draw.rectangle((180+n*10,60,300+n*10,120),fill='#263f39')
        draw.rectangle((175+n*10,250,305+n*10,340),fill='#f0da9a')
        draw.text((195+n*10,285),'TEST ONLY',fill='black')
        image.save(directory/f'synthetic-bottle-{n+1}.png')
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8017,access_log=False)


if __name__=='__main__':main()
