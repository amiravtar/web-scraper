import os
from pathlib import Path
import subprocess
import logging
import time
from requests import Request, Session
import re
from functools import wraps

def time_execution(func):
    @wraps(func)
    def timeit_wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        total_time = (end_time - start_time) / 60
        logging.info(f"Function {func.__name__} Took {total_time:.2f} seconds")
        return result

    return timeit_wrapper


cwd = Path(__file__).parent.resolve()
os.chdir(cwd)

logging.basicConfig(
    filename="procces_data.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
# spider settings
SHOW_EXIST = True
OUTPUT = cwd / "out.csv"
OUTPUT_ERROR = cwd / "app_error.log"
LOG_LVEL = "ERROR"


# sync setting
SITE_URL = "http://localhost/wordpress_empty/"
WO_LOGIN = "wp-login.php"
WO_ADMIN = "wp-admin/"

TESTCOOKIE = "1"
WP_SUBMIT = "ورود"

WO_ADMIN_DASH = SITE_URL + WO_ADMIN

PRODUCTS = WO_ADMIN_DASH + "edit.php?post_type=product"
WP_IMPORT_PAGE = WO_ADMIN_DASH + "edit.php?post_type=product&page=product_importer"
WP_EDIT_PHP = WO_ADMIN_DASH + "edit.php"
WP_ADMIN_AJAX = WO_ADMIN_DASH + "admin-ajax.php"
# PROXY = {
#     "http": "http://localhost:8080",
#     "https": "http://localhost:8080",
# }
LOGIN_USERNAME = "admin"
LOGIN_PASSWORD="pass"
# PWD = "123"

@time_execution
def run_spider():
    logging.info("Running spider")
    start_time = time.time()
    with open(OUTPUT_ERROR, "a") as f:
        pro = subprocess.Popen(
            [
                "scrapy",
                "crawl",
                "main_spider",
                "-a",
                f"show_exist={SHOW_EXIST}",
                "-O",
                f"{OUTPUT}",
                "-L",
                f"{LOG_LVEL}",
            ],
            stderr=f,
            stdout=f,
        )
        pro.wait()
    end_time = time.time()
    logging.info(f"Spider ran in {(end_time-start_time)/60:.2f}")


def get_wpnonce(text: str):
    hint = 'name="_wpnonce" value="'
    i = text.find(hint)
    start_index = i + len(hint)
    return text[start_index : start_index + 10]


def get_security(text: str):
    hint = '"import_nonce":"'
    i = text.find(hint)
    start_index = i + len(hint)
    return text[start_index : start_index + 10]


def get_position(text: str):
    res = re.search('(position":)(\d*)', text)
    if res.group(2) != "":
        return res.group(2)
    else:
        return None

@time_execution
def sync_with_wordpress():
    logging.info("Syncing with wordpress")
    login_data = {
        "log": LOGIN_USERNAME,
        "pwd": LOGIN_PASSWORD,
        "wp-submit": WP_SUBMIT,
        "redirect_to": SITE_URL + WO_ADMIN,
        "testcookie": TESTCOOKIE,
    }
    s = Session()
    r = s.post(url=SITE_URL + WO_LOGIN, data=login_data)
    if r.ok:
        logging.info(f"Logged in with code {r.status_code}")

    file_upload_params = {
        "post_type": "product",
        "page": "product_importer",
    }
    for i in ["1", "0"]:
        update_exist = i
        logging.info(f"import with update_exist {update_exist}")
        file_upload_file = {
            "import": open(OUTPUT, "rb"),
        }

        import_page = s.get(url=WP_EDIT_PHP, params=file_upload_params)
        logging.info("Getting import page")

        nonce = get_wpnonce(import_page.text)
        logging.info(f"Got import page with wpnonce {nonce}")

        file_upload_data = {
            "action": "save",
            "max_file_size": "8388608",
            "update_existing": update_exist,
            "save_step": "Continue",
            "delimiter": "",
            "file_url": "",
            "file_url": "",
            "_wp_http_referer": WP_IMPORT_PAGE,
            "_wpnonce": nonce,
        }
        logging.info("Uploading Data file to wordpress")
        req = Request(
            "POST",
            url=WP_EDIT_PHP,
            params=file_upload_params,
            data=file_upload_data,
            files=file_upload_file,
            cookies=s.cookies,
        )
        req = req.prepare()
        r = s.send(req, allow_redirects=False)

        if r.is_redirect:
            t = r.next
            temp = t.url.split("&")
            file = ""
            for i in temp:
                if i.find("file") != -1:
                    file = i[5:]
            logging.info(f"File Uploaded with name {file}")
            import_params = {
                "post_type": "product",
                "page": "product_importer",
                "step": "import",
                "delimiter": ",",
                "update_existing": update_exist,
                "file": file,
                "_wpnonce": nonce,
            }
            import_data = {
                "map_from[0]": "Categories",
                "map_to[0]": "category_ids",
                "map_from[1]": "Description",
                "map_to[1]": "description",
                "map_from[2]": "Images",
                "map_to[2]": "images",
                "map_from[3]": "In_stock",
                "map_to[3]": "stock_status",
                "map_from[4]": "Name",
                "map_to[4]": "name",
                "map_from[5]": "Published",
                "map_to[5]": "published",
                "map_from[6]": "Regular_price",
                "map_to[6]": "regular_price",
                "map_from[7]": "SKU",
                "map_to[7]": "sku",
                "map_from[8]": "Short_description",
                "map_to[8]": "short_description",
                "save_step": "Run the importer",
                "file": file,
                "delimiter": ",",
                "update_existing": update_exist,
                "_wpnonce": nonce,
            }
            logging.info("Submitting Import")
            req = Request(
                "POST",
                url=WP_EDIT_PHP,
                params=import_params,
                data=import_data,
                cookies=s.cookies,
            )
            req = req.prepare()
            r = s.send(req, allow_redirects=False)

            if r.status_code == 200:
                security = get_security(r.text)
                logging.info(f"Import Submitted with security {security}")
                position = 0
                while position is not None:
                    logging.info(f"Submitting to admin ajax with {position}")
                    import_data = {
                        "action": "woocommerce_do_ajax_product_import",
                        "position": str(position),
                        "mapping[from][0]": "Categories",
                        "mapping[from][1]": "Description",
                        "mapping[from][2]": "Images",
                        "mapping[from][3]": "In_stock",
                        "mapping[from][4]": "Name",
                        "mapping[from][5]": "Published",
                        "mapping[from][6]": "Regular_price",
                        "mapping[from][7]": "SKU",
                        "mapping[from][8]": "Short_description",
                        "mapping[to][0]": "category_ids",
                        "mapping[to][1]": "description",
                        "mapping[to][2]": "images",
                        "mapping[to][3]": "stock_status",
                        "mapping[to][4]": "name",
                        "mapping[to][5]": "published",
                        "mapping[to][6]": "regular_price",
                        "mapping[to][7]": "sku",
                        "mapping[to][8]": "short_description",
                        "file": file,
                        "update_existing": update_exist,
                        "delimiter": ",",
                        "security": security,
                    }

                    req = Request(
                        "POST", url=WP_ADMIN_AJAX, data=import_data, cookies=s.cookies
                    )
                    req = req.prepare()
                    r = s.send(req)
                    logging.info(
                        f"Submited to admin ajax with position {position} and responce {r.status_code}"
                    )

                    position = get_position(r.text)
                    logging.info(r.text)
                logging.info("Finished Submitting to admin ajax with return")


run_spider()
#sync_with_wordpress()
