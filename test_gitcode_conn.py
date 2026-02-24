import sys
import os
import logging
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'skills', 'project-manager', 'src'))

from connectors.gitcode import GitCodeConnector

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GitCodeTest")

# Load env
load_dotenv()

def test_connection():
    token = os.getenv("GITCODE_TOKEN")


    if not token:
        logger.error("No GITCODE_TOKEN found in environment.")
        return

    logger.info(f"Token found: {token[:4]}...{token[-4:]}")
    
    connector = GitCodeConnector(logger=logger)
    logger.info("Checking authentication...")
    
    if connector.check_auth():
        logger.info("✅ SUCCESS: Connected to GitCode API successfully!")
    else:
        logger.error("❌ FAILED: Could not authenticate with GitCode.")

if __name__ == "__main__":
    test_connection()
