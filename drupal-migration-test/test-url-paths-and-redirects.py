# import pytest
from playwright.sync_api import sync_playwright, Response
import time
from datetime import datetime

import csv

## CHANGE the server urls here

operations_portal_old_server = "https://operations.access-ci.org"
# operations_portal_new_server = "https://beta-operations.access-ci.org"
operations_portal_new_server = "https://cms1.operations.access-ci.org"

operations_portal_url_checks = []
with open('access-operations-portal-url-paths.csv', mode='r', encoding='utf-8') as file:
    reader = csv.reader(file)
    for row in reader:
        operations_portal_url_checks.append(row)

operations_portal_url_checks_header = operations_portal_url_checks[0]
operations_portal_url_checks = operations_portal_url_checks[1:] #[18:19]  #


def analyze_url(server, url: str):
    url = url.rstrip('/ ')

    with sync_playwright() as p:
        # headless browser
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # statistics
        redirects = []
        page_size_bytes = 0

        # Listen to all network responses to calculate total page size
        def handle_response(response: Response):
            nonlocal page_size_bytes
            try:
                # Accumulate the size of all assets (HTML, JS, CSS, Images, etc.)
                body = response.body()
                page_size_bytes += len(body)
            except Exception:
                # Skip if body cannot be read (e.g., failed requests or certain content types)
                pass

        page.on("response", handle_response)

        # redirection flow
        def handle_request(request):
            if request.redirected_from and request.url.rstrip('/ ') != url:
                redirects.append({
                    "from": request.redirected_from.url.replace(server, "").rstrip('/ '),
                    "to": request.url.replace(server, "").rstrip('/ ')
                })

        page.on("request", handle_request)

        start_time = time.time()
        response = None
        status_code = None
        try:
            # Navigate to the URL
            response = page.goto(url, wait_until="networkidle")

            # Extract status code
            status_code = response.status if response else None
        except:
            pass

        end_time = time.time()
        load_time_ms = (end_time - start_time) * 1000

        browser.close()

        return {
            "url_absolute": url,
            "url": url.replace(server, "").rstrip('/ '),
            "final_url": page.url.replace(server, "").rstrip('/ '),
            "status_code": status_code,
            "load_time_ms": load_time_ms,
            "total_size_kb": round(page_size_bytes / 1024, 2),
            "redirects": redirects
        }


def validate_servers():
    results_file_name = f"results-{datetime.now().strftime('%Y-%m-%d_%H:%M:%S')}.csv"

    total_pages = len(operations_portal_url_checks)
    total_pages_not_found = 0
    total_redirects = 0
    total_redirects_errors = 0

    with open(results_file_name, mode='w', encoding='utf-8', newline='') as csv_file:
        writer = csv.writer(csv_file)

        columns = [
            {"name": "URL", "variable": "url_absolute"},
            {"name": "Final URL/Path", "variable": "final_url"},
            {"name": "Status Code", "variable": "status_code"},
            {"name": "Load time (ms)", "variable": "load_time_ms"},
            {"name": "Size (kb)", "variable": "total_size_kb"}
        ]

        writer.writerow(
            operations_portal_url_checks_header +
            [f"Old server {column['name']}" for column in columns] +
            [f"New server {column['name']}" for column in columns]
        )

        all_errors_str = ""

        for i in range(len(operations_portal_url_checks)):
            operations_portal_url_check = operations_portal_url_checks[i]
            errors = []

            url_path = operations_portal_url_check[0]
            has_redirect = operations_portal_url_check[2]
            expected_redirect_url = operations_portal_url_check[3]

            old_server_result = analyze_url(operations_portal_old_server, f"{operations_portal_old_server}{url_path}")
            new_server_result = analyze_url(operations_portal_new_server, f"{operations_portal_new_server}{url_path}")

            if has_redirect == "Yes":
                total_redirects += 1

                if len(new_server_result['redirects']) == 0:
                    errors.append("The redirection is not implemented in the new server")
                    total_redirects_errors += 1
                elif old_server_result['final_url'] != new_server_result['final_url']:
                    errors.append("The redirected URLs do not match")
                    total_redirects_errors += 1
                elif expected_redirect_url not in [r["to"] for r in new_server_result['redirects']]:
                    total_redirects_errors += 1
                    errors.append(
                        f"The new server redirect url does not match the expected redirect url ({expected_redirect_url})")
            else:
                if new_server_result['status_code'] is not None and new_server_result['status_code'] >= 400:
                    errors.append("The page doesn't exist in the new server")
                    total_pages_not_found += 1
                elif old_server_result['status_code'] != new_server_result['status_code']:
                    errors.append("The status codes do not match")

            writer.writerow(
                operations_portal_url_check +
                [old_server_result[column['variable']] for column in columns] +
                [new_server_result[column['variable']] for column in columns]
            )

            error_str = "".join([f"\n\t {i + 1}) {errors[i]}" for i in range(len(errors))])

            if len(errors) > 0:
                all_errors_str += f"\n   {new_server_result['url']} \033[91m{error_str}\033[0m"
                error_str = f"\033[91m  Errors:  {error_str} \033[0m"

            print(f"""
#######################################################
--- Statistics for {url_path} --- ({i + 1} of {len(operations_portal_url_checks)})
  URL: \t{old_server_result['url_absolute']}\t-->\t{new_server_result['url_absolute']}
  Final URL/path: \t{old_server_result['final_url']}\t-->\t{new_server_result['final_url']}
  Status Code:      \t{old_server_result['status_code']}\t\t\t-->\t{new_server_result['status_code']}
  Page Load Time:  \t{old_server_result['load_time_ms']:.2f} ms\t\t-->\t{new_server_result['load_time_ms']:.2f} ms
  Page Size:       \t{old_server_result['total_size_kb']} KB\t\t-->\t{new_server_result['total_size_kb']} KB
{error_str}
            """)

    print(f"""
Successfully wrote {len(operations_portal_url_checks)} results to {results_file_name}

{"Summary of errors:" if len(all_errors_str) > 0 else ""}{all_errors_str}

Summary:
    Page not found : {total_pages_not_found}/{total_pages}
    Redirect not working : {total_redirects_errors}/{total_redirects}
    """)


validate_servers()
