import os
import datetime
import logging
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

def generate_mqtt_certificates(base_dir=None):
    """
    Generate MQTT broker certificates
    :param base_dir: Base directory to save certificates (optional)
    :return: Dictionary of file paths for certificates
    """
    try:
        # If no base directory is provided, use the project's root directory
        if base_dir is None:
            base_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'config'
            )
        
        # Create a specific directory for MQTT certificates
        cert_dir = os.path.join(base_dir, 'mqtt_certificates')
        os.makedirs(cert_dir, exist_ok=True)
        
        logging.info(f"Certificate directory: {cert_dir}")
        
        # Generate CA key and certificate
        ca_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        ca_subject = x509.Name([
            x509.NameAttribute(x509.NameOID.COMMON_NAME, u"MQTT Broker CA"),
            x509.NameAttribute(x509.NameOID.ORGANIZATION_NAME, u"Home MQTT Infrastructure"),
            x509.NameAttribute(x509.NameOID.COUNTRY_NAME, u"LT"),
        ])
        
        ca_cert = (
            x509.CertificateBuilder()
            .subject_name(ca_subject)
            .issuer_name(ca_subject)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=None),
                critical=True
            )
            .sign(ca_key, hashes.SHA256(), default_backend())
        )
        
        # Generate server key and certificate
        server_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        server_subject = x509.Name([
            x509.NameAttribute(x509.NameOID.COMMON_NAME, u"mqtt.local"),
            x509.NameAttribute(x509.NameOID.ORGANIZATION_NAME, u"Home MQTT Infrastructure"),
            x509.NameAttribute(x509.NameOID.COUNTRY_NAME, u"LT"),
        ])
        
        server_cert = (
            x509.CertificateBuilder()
            .subject_name(server_subject)
            .issuer_name(ca_cert.subject)
            .public_key(server_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName('mqtt.local')]),
                critical=False
            )
            .sign(ca_key, hashes.SHA256(), default_backend())
        )
        
        # Define file paths
        ca_cert_path = os.path.join(cert_dir, "ca.crt")
        server_cert_path = os.path.join(cert_dir, "server.crt")
        server_key_path = os.path.join(cert_dir, "server.key")
        
        # Save CA certificate
        with open(ca_cert_path, "wb") as f:
            f.write(ca_cert.public_bytes(serialization.Encoding.PEM))
        logging.info(f"CA certificate saved to {ca_cert_path}")
        
        # Save server certificate
        with open(server_cert_path, "wb") as f:
            f.write(server_cert.public_bytes(serialization.Encoding.PEM))
        logging.info(f"Server certificate saved to {server_cert_path}")
        
        # Save server private key with restricted permissions
        with open(server_key_path, "wb") as f:
            f.write(server_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        logging.info(f"Server key saved to {server_key_path}")
        
        # Set secure permissions for key file
        os.chmod(server_key_path, 0o600)
        
        # Return dictionary of file paths
        return {
            'ca_file': ca_cert_path,
            'certificate_file': server_cert_path,
            'key_file': server_key_path
        }
    
    except Exception as e:
        logging.error(f"Certificate generation failed: {e}")
        raise

def prepare_mqtt_certificates(config_certificates):
    """
    Prepare MQTT certificates, generating only if specified files don't exist
    
    Args:
        config_certificates (dict): Dictionary with certificate file paths
    
    Returns:
    dict: Paths to certificate files (generated or existing)
    """
    # Extract file paths from configuration
    ca_file = config_certificates.get('ca_file')
    cert_file = config_certificates.get('certificate_file')
    key_file = config_certificates.get('key_file')

    # Check if all specified files exist
    if (ca_file and os.path.exists(ca_file) and 
        cert_file and os.path.exists(cert_file) and 
        key_file and os.path.exists(key_file)):
        print("All certificate files already exist. No generation needed.")
        return config_certificates

    # If any file is missing, determine the base directory for generation
    base_dir = os.path.dirname(ca_file) if ca_file else None

    # Generate certificates
    generated_certs = generate_mqtt_certificates(base_dir)

    # Rename generated files to match the expected paths if specified
    if ca_file:
        os.rename(generated_certs['ca_file'], ca_file)
        generated_certs['ca_file'] = ca_file
    if cert_file:
        os.rename(generated_certs['certificate_file'], cert_file)
        generated_certs['certificate_file'] = cert_file
    if key_file:
        os.rename(generated_certs['key_file'], key_file)
        generated_certs['key_file'] = key_file

    return generated_certs