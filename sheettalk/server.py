import argparse
from datetime import datetime
from dateutil import tz

from flask import Flask, request, redirect
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

def get_mapping_sheet(gc, fname):
    try:
        sh = gc.open(fname)
    except gspread.exceptions.SpreadsheetNotFound:
        sh = gc.create(fname)
        if args.admin_email:
            sh.share(args.admin_email, perm_type='user', role='writer')
    return sh.sheet1

def set_mapping(mapping_sheet, number, url):
    numbers = mapping_sheet.col_values(1)
    if number in numbers:
        row = numbers.index(number) + 1
    else:
        row = len(numbers) + 1
    mapping_sheet.insert_row([number, url], index=row)

def process_message(number, message_body):
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    credentials = ServiceAccountCredentials.from_json_keyfile_name(args.credentials, scope)
    gc = gspread.authorize(credentials)
    mapping_sheet = get_mapping_sheet(gc, "sheettalk mapping")
    # If the text is a spreadsheet url, save number -> url mapping.
    if message_body.startswith("http"):
        try:
            set_mapping(mapping_sheet, number, message_body)
        except:
            return "Could not set sheet".format(message_body)
        return "Sheet now {}.".format(message_body)
    # Otherwise, aim to update the user's sheet with the content.
    else:
        # Get the current time.
        tz_from = tz.gettz('UTC')
        tz_to = tz.gettz('America/New_York')
        time = datetime.utcnow().replace(tzinfo=tz_from).astimezone(tz_to)
        time = time.strftime("%Y-%m-%d %H:%M:%S")
        # Get the sheet url and then the sheet.
        mapping = dict(mapping_sheet.get_all_values())
        try:
            url = mapping[number]
        except:
            return "Sheet not set for number {}".format(number)
        try:
            user_sheet = gc.open_by_url(url).sheet1
        except:
            return "Could not open user sheet {}".format(url)
        # Get the proper row and columns for the time and data.
        try:
            headers = [v.lower() for v in user_sheet.row_values(1)]
            header, value = message_body.split(" ", 1)
        except:
            return "Could not parse user sheet {}".format(url)
        if header.lower() not in headers:
            return "{} not in sheet headers".format(header)
        if "time" not in headers:
            return "'time' not in sheet headers"
        data_col = headers.index(header.lower()) + 1
        time_col = headers.index("time") + 1
        row = len(user_sheet.get_all_values()) + 1
        # Insert.
        user_sheet.update_cell(row, time_col, time)
        user_sheet.update_cell(row, data_col, value)
        return "Updated {}".format(header)

@app.route("/sms", methods=['GET', 'POST'])
def sms_reply():
    # Process message and construct response.
    try:
        response_body = process_message(request.form['From'], request.form['Body'])
    except Exception as e:
        response_body = "Could not process. Error: {}".format(e)
    # Construct and send TwiML response.
    print("sending " + response_body)
    response = MessagingResponse()
    response.message(response_body)
    return str(response)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='.')
    parser.add_argument("--credentials", help="Credentials file.",
                        default="credentials.json")
    parser.add_argument("--admin-email", help="Admin email.")
    args = parser.parse_args()
    
    app.run(debug=True)
