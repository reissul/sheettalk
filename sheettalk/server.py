import argparse
from datetime import datetime
from dateutil import tz

from flask import Flask, request, redirect
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import simplejson
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

def get_mapping_sheet(gc, fname):
    try:
        sh = gc.open(fname)
    except gspread.exceptions.SpreadsheetNotFound:
        sh = gc.create(fname)
    if args.admin_email:
        sh.share(args.admin_email, "user", "writer", notify=False)
    return sh.sheet1


def set_mapping(mapping_sheet, number, url):
    numbers = mapping_sheet.col_values(1)
    if number in numbers:
        row = numbers.index(number) + 1
    else:
        row = len(numbers) + 1
    mapping_sheet.delete_row(row)
    mapping_sheet.insert_row([number, url], index=row)


def process_message(number, message_body):
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    creds_dict = simplejson.load(open(args.credentials))
    creds = ServiceAccountCredentials.from_json_keyfile_name(args.credentials,
                                                             scope)
    gc = gspread.authorize(creds)
    mapping_sheet = get_mapping_sheet(gc, "sheettalk mapping")
    # If the text is a spreadsheet url, save number -> url mapping.
    if message_body.startswith("http"):
        set_mapping(mapping_sheet, number, message_body)
        return('Spreadsheet set! Enter a column name, a space, and a value '
               'to update the column with that time-stamped value.')
    # Otherwise, update the user's sheet with the content.
    else:
        # Get the sheet url and then the sheet.
        mapping = dict(mapping_sheet.get_all_values())
        try:
            url = mapping[number]
        except KeyError:
            return('No spreadsheet set for {}. Text the url of the Google Sheet '
                   'you would like to edit.'.format(number))
        perm_err = ('Do not have permission to edit. Please "share" with {}.'
                    .format(creds_dict["client_email"]))
        try:
            user_spreadsheet = gc.open_by_url(url)
            user_sheet = user_spreadsheet.sheet1
        except gspread.exceptions.APIError:
            return(perm_err)
        properties = user_spreadsheet.fetch_sheet_metadata()["properties"]
        perm_err = ('Do not have permission to edit "{}." Please "share" with {}.'
                    .format(properties["title"], creds_dict["client_email"]))
        # If the text is "undo" then delete last row and return.
        if message_body.strip().lower() == "undo":
            last_row = len(user_sheet.get_all_values())
            if last_row <= 1:
                return("No rows to undo!")
            try:
                user_sheet.delete_row(last_row)
            except gspread.exceptions.APIError:
                return(perm_err)
            return("Undid last row.")
        # Get the user sheet time zonne and use it to set the current time.
        tz_to = tz.gettz(properties["timeZone"])
        tz_from = tz.gettz('UTC')
        time = datetime.utcnow().replace(tzinfo=tz_from).astimezone(tz_to)
        time = time.strftime("%Y-%m-%d %H:%M:%S")
        # Get the proper row and columns for the time and data.
        headers = [v.lower() for v in user_sheet.row_values(1)]
        header, value = message_body.split(" ", 1)
        if header.lower() not in headers:
            return('{} not in sheet headers.'.format(header))
        if header.lower() == "time":
            return('Cannot update "time" column.')
        if "time" not in headers:
            return('"time" not in sheet headers.')
        data_col = headers.index(header.lower()) + 1
        time_col = headers.index("time") + 1
        row = len(user_sheet.get_all_values()) + 1
        # Insert.
        try:
            user_sheet.update_cell(row, time_col, time)
            user_sheet.update_cell(row, data_col, value)
        except gspread.exceptions.APIError:
            return(perm_err)
        return('Added to column {}.'.format(header))


@app.route("/sms", methods=['GET', 'POST'])
def sms_reply():
    # Process message and construct response.
    try:
        response_body = process_message(request.form['From'], request.form['Body'])
    except Exception as e:
        response_body = "Could not process message"
        print(e)
    # Construct and send TwiML response.
    print(response_body)
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
