import argparse
from datetime import datetime
from dateutil import tz
import re

from flask import Flask, request, redirect
from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from twilio.twiml.messaging_response import MessagingResponse

from config_db import Base, User, Spreadsheet

app = Flask(__name__)

def get_column_headers(sheets_api, spreadsheet_id):
    result = sheets_api.values().get(spreadsheetId=spreadsheet_id,
                                     range='Data!A1:Z1',
                                     majorDimension="COLUMNS").execute()
    a = result.get('values', [])
    return {v[0].lower():i for i,v in enumerate(result.get('values', []))}
    
def get_user(session, number):
    return session.query(User).filter(User.number == number).first()

def insert_user(session, number):
    user = User(number=number)
    session.add(user)
    session.commit()

def get_spreadsheets_api():
    store = file.Storage('token.json')
    creds = store.get()
    if not creds or creds.invalid:
        flow = client.flow_from_clientsecrets('credentials.json', SCOPES)
        creds = tools.run_flow(flow, store)
    service = build('sheets', 'v4', http=creds.authorize(Http()))
    return service.spreadsheets()

def get_spreadsheet(session, user):
    return session.query(Spreadsheet).filter(Spreadsheet.user == user).first()

def get_spreadsheets_(sheets_api, spreadsheet_id):
    request = sheets_api.get(spreadsheetId=spreadsheet_id)
    response = request.execute()
    return response["title"]

def insert_spreadsheet(session, user, spreadsheet_google_id):
    spreadsheet = Spreadsheet(spreadsheet_google_id=spreadsheet_google_id,
                              user=user)
    session.add(spreadsheet)
    session.commit()

def update_spreadsheet(sheets_api, spreadsheet_id, column, value, column_headers):
    tz_from = tz.gettz('UTC')
    tz_to = tz.gettz('America/New_York')
    dt = datetime.utcnow().replace(tzinfo=tz_from).astimezone(tz_to)
    values = [None for _ in column_headers]
    values[column_headers["time"]] = dt.strftime("%Y-%m-%d %H:%M:%S")
    values[column_headers[column.lower()]] = value
    body = {'values': [values]}
    request = sheets_api.values().append(spreadsheetId=spreadsheet_id,
                                         range='Data!A1:Z1',
                                         valueInputOption="USER_ENTERED",
                                         body=body)
    response = request.execute()

def process_message(number, message_body):

    print("DEBUG 0")
    sheets_api = get_spreadsheets_api()
    session = DBSession()
    print("DEBUG 1")

    # Get or create User.
    user = get_user(session, number)
    if user is None:
        user = insert_user(session, number)
    print("DEBUG 2")
    
    # Get any existing spreadsheet and column_headers
    print("DEBUG 2.1")
    spreadsheet = get_spreadsheet(session, user)
    print("DEBUG 2.2")
    if spreadsheet:
        print("DEBUG 2.3")
        column_headers = get_column_headers(sheets_api, spreadsheet.spreadsheet_google_id)
        print("DEBUG 2.4")
    else:
        column_headers = None
    print("DEBUG 3")

    # If spreadsheet url, insert Spreadsheet in db.
    #re_search_url = re.search("/d/(.+)/edit#gid=(\d+)", message_body)
    re_search_url = re.search("/d/(.+)", message_body)
    print("DEBUG 4")
    print(str(column_headers))
    print(message_body.split()[0])
    print(message_body.split()[0] in column_headers)
    if re_search_url:
        spreadsheet_google_id = re_search_url.group(1)
        insert_spreadsheet(session, user, spreadsheet_google_id)
        #title = get_spreadsheets_title(sheets_api, spreadsheet_id)
        response_body = "Spreadsheet now '{}'.".format(message_body)
    # If column message, update Spreadsheet in Google Docs.
    elif column_headers and message_body.split()[0].lower() in column_headers:
        print("A")
        column, value = message_body.split(" ", 1)
        print("B")
        update_spreadsheet(sheets_api, spreadsheet.spreadsheet_google_id,
                           column, value, column_headers)
        print("C")
        response_body = "Updated {}.".format(column)
        print("D")
    else:
        response_body = "Unknown format! Try '<url>' or '<column> <value>'."

    return response_body

@app.route("/sms", methods=['GET', 'POST'])
def sms_reply():

    # Process message and construct response.
    try:
        response_body = process_message(request.form['From'], request.form['Body'])
    except Exception as e:
        response_body = "Could not process. Error: {}".format(e)
    
    # Construct and send TwiML response.
    resp = MessagingResponse()
    resp.message(response_body)
    print("sending " + response_body)
    return str(resp)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='.')
    parser.add_argument("--db", help="Db name.", default="sheettalk")
    args = parser.parse_args()

    # Init session.
    engine = create_engine('sqlite:///{}.db'.format(args.db))
    Base.metadata.bind = engine
    DBSession = sessionmaker()
    DBSession.bind = engine
    #session = DBSession()

    app.run(debug=True)
