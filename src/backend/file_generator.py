import os
import logging
from src.utils.logger import setup_logger
logger = setup_logger()

def create_acl_file(config):
    """
    Create ACL file from configuration
    Args:
        config (dict): Configuration containing ACL rules and file location
    Returns:
        str: Path to the created ACL file
    """
    try:
        if not config or 'rules' not in config or 'acl_file_location' not in config:
            logger.error("Missing required ACL configuration")
            return None

        file_path = config['acl_file_location']
        rules = config['rules']

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Write rules to file
        with open(file_path, 'w') as f:
            for rule in rules:
                f.write(f"{rule}\n")

        logger.info(f"Created ACL file at: {file_path}")
        return file_path

    except Exception as e:
        logger.error(f"Failed to create ACL file: {str(e)}")
        raise

def create_password_file(config):
    """
    Create password file from configuration
    Args:
        config (dict): Configuration containing user credentials and file location
    Returns:
        str: Path to the created password file
    """
    try:
        if not config or 'users' not in config or 'password_file_location' not in config:
            logger.error("Missing required password file configuration")
            return None

        file_path = config['password_file_location']
        users = config['users']

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Write credentials to file
        with open(file_path, 'w') as f:
            for username, password in users.items():
                f.write(f"{username}:{password}\n")

        logger.info(f"Created password file at: {file_path}")
        return file_path

    except Exception as e:
        logger.error(f"Failed to create password file: {str(e)}")
        raise