import subprocess, sys, os

out = os.path.join(os.path.dirname(__file__), "..", "certs")
os.makedirs(out, exist_ok=True)

key = os.path.join(out, "key.pem")
cert = os.path.join(out, "cert.pem")

candidates = [
    "openssl",
    r"C:\Program Files\Git\usr\bin\openssl.exe",
    r"C:\Program Files (x86)\Git\usr\bin\openssl.exe",
]

openssl = None
for c in candidates:
    try:
        subprocess.run([c, "version"], capture_output=True, check=True)
        openssl = c
        break
    except Exception:
        pass

if openssl is None:
    print("openssl not found -- trying python cryptography library")
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime

        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
        cert_obj = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
            .sign(private_key, hashes.SHA256())
        )
        with open(key, "wb") as f:
            f.write(private_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
        with open(cert, "wb") as f:
            f.write(cert_obj.public_bytes(serialization.Encoding.PEM))
        print(f"certs written to {out}")
        sys.exit(0)
    except ImportError:
        pass

    print("ERROR: install cryptography with:  pip install cryptography")
    print("Then run this script again.")
    sys.exit(1)

subprocess.run([
    openssl, "req", "-x509", "-nodes", "-days", "365",
    "-newkey", "rsa:2048",
    "-keyout", key,
    "-out", cert,
    "-subj", "/CN=localhost/O=tabular-analytics"
], check=True)
print(f"certs written to {out}")
