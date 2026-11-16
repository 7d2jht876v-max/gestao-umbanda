"""Generate a local CA once and a server certificate for current LAN addresses."""
import argparse,datetime as dt,ipaddress,socket
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from server import addresses

def generate(data):
    root=Path(data)/'certificados';root.mkdir(parents=True,exist_ok=True)
    now=dt.datetime.now(dt.timezone.utc)
    ca_key_path=root/'ca-key.pem';ca_path=root/'ca.pem'
    if ca_key_path.exists() and ca_path.exists():
        ca_key=serialization.load_pem_private_key(ca_key_path.read_bytes(),password=None)
        ca=x509.load_pem_x509_certificate(ca_path.read_bytes())
    else:
        ca_key=rsa.generate_private_key(public_exponent=65537,key_size=3072)
        name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Templo Xango - Notebook local')])
        ca=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(ca_key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-dt.timedelta(minutes=5)).not_valid_after(now+dt.timedelta(days=3650)).add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True).add_extension(x509.KeyUsage(digital_signature=True,key_encipherment=False,key_cert_sign=True,key_agreement=False,content_commitment=False,data_encipherment=False,crl_sign=True,encipher_only=False,decipher_only=False),critical=True).sign(ca_key,hashes.SHA256()))
        ca_key_path.write_bytes(ca_key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        ca_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    names=[x509.DNSName('localhost'),x509.DNSName(socket.gethostname())]+[x509.IPAddress(ipaddress.ip_address(ip)) for ip in addresses()]
    cert=(x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Gestao Umbanda - Notebook')])).issuer_name(ca.subject).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-dt.timedelta(minutes=5)).not_valid_after(now+dt.timedelta(days=365)).add_extension(x509.SubjectAlternativeName(names),critical=False).add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True).add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),critical=False).sign(ca_key,hashes.SHA256()))
    (root/'server-key.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    (root/'server.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM)+ca.public_bytes(serialization.Encoding.PEM))
    public=root/'CA-Templo-Xango.cer';public.write_bytes(ca.public_bytes(serialization.Encoding.DER))
    for private in (ca_key_path,root/'server-key.pem'):
        try: private.chmod(0o600)
        except OSError: pass
    print('Certificados criados. Certificado PUBLICO para o iPhone: '+str(public.resolve()))
    print('Impressao digital SHA256: '+ca.fingerprint(hashes.SHA256()).hex(':'))
    return root
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',default=str(Path(__file__).parent/'dados'));generate(p.parse_args().data)
