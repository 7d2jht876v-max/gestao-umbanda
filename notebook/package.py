"""Package source plus existing web assets, never user data or credentials."""
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parent.parent
out=ROOT.parent/'Gestao-Umbanda-Notebook-1.0.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    for name in ['server.py','certificates.py','requirements.txt','INSTALAR.bat','INICIAR.bat','LEIA-PRIMEIRO.html']:
        z.write(ROOT/'notebook'/name,'Gestao-Umbanda-Notebook/'+name)
    for name in ['index.html','manifest.webmanifest','install.js','baralho-cigano.html']:
        z.write(ROOT/name,'Gestao-Umbanda-Notebook/web/'+name)
    for name in ['notebook-client.js','manage.html','offline-worker.js']:
        z.write(ROOT/'notebook'/name,'Gestao-Umbanda-Notebook/web/notebook/'+name)
    for p in (ROOT/'icons').glob('*.png'):
        z.write(p,'Gestao-Umbanda-Notebook/web/icons/'+p.name)
print(out)
