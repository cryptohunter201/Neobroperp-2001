import os
import requests

def send_wa_alert(pesan: str):
    """
    Kirim WA via Fonnte - tinggal panggil ini pas fail ASTER dll
    """
    token = os.getenv("FONNTE_TOKEN", "gDw4kSGUhL4UkHzN8Jc7")
    target = os.getenv("FONNTE_TARGET", "6282227097005")
    
    if not token or not target:
        print("FONNTE_TOKEN / TARGET belum di set")
        return

    try:
        r = requests.post(
            "https://api.fonnte.com/send",
            headers={"Authorization": token},
            data={
                "target": target,
                "message": pesan,
                "countryCode": "62",
                "delay": "2"
            },
            timeout=15
        )
        print(f"Fonnte response: {r.text}")
    except Exception as e:
        print(f"Fonnte error: {e}")
