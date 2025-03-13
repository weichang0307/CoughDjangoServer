import os
from django.conf import settings

# Setup Django environment if running outside of Django shell
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CoughToMusicDjango.settings')

import django
django.setup()

\
# Set test parameters
pubCoughID = '1'  # Replace with an existing pubCoughID that has a cough wav in PUBLIC_COUGH
instrument_type = 'string'  # or 'wind'
sample_rate = 16000

def run_test_pipeline(pubCoughID, instrument_type, sample_rate):
    try:
        print(f"Running cough2midi for pubCoughID={pubCoughID}")
        cough2midi(pubCoughID)

        print(f"Running generate_trio_mid for pubCoughID={pubCoughID}")
        generate_trio_mid(pubCoughID)

        print(f"Running generate_trio_trk for pubCoughID={pubCoughID}")
        generate_trio_trk(pubCoughID, instrument_type, sample_rate=sample_rate)

        print("✅ Pipeline test completed successfully.")

    except Exception as e:
        print(f"❌ Error during pipeline test: {e}")

# Run it
run_test_pipeline(pubCoughID, instrument_type, sample_rate)
