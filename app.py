import re
import bcrypt
import flask_login
import json
import logging
import os
import pyrebase

import threading
from dotenv import load_dotenv
from helpers import *
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, redirect, request, render_template, redirect, url_for

load_dotenv()

tars_token = os.environ.get("TARS_TOKEN")  # Bot user OAuth
tars_user_token = os.environ.get("TARS_USER_TOKEN")  # User OAuth
tars_admin = os.environ.get("TARS_ADMIN")  # Channel for testing
tars_secret = os.environ.get("TARS_SECRET")  # signing secret

firebase_api_key = os.environ.get("FIREBASE_API_KEY")  # Firebase API key
tars_fb_ad = os.environ.get("TARS_FB_AD")  # Firebase authDomain
tars_fb_url = os.environ.get("TARS_FB_URL")  # Firebase databaseURL
tars_fb_sb = os.environ.get("TARS_FB_SB")  # Firebase storageBucket
key_fb_tars = os.environ.get("KEY_FB_TARS")  # SHA used to access child

vineethv_id = os.environ.get("VINEETHV_ID")  # Sir's user ID
general = os.environ.get("GENERAL_ID")  # `general` channel ID
tars = os.environ.get("TARS_ID")  # TARS ID
vineeth_emailid = os.environ.get("VINEETH_EMAIL_ID")  # Sir's email ID

username = os.environ.get("USERNAME")  # Webpage login username
password = os.environ.get("PASSWORD").encode()  # Webpage login password
secret = os.environ.get("SECRET")  # Don't change

office_hours_form_url = os.environ.get(
    "OFFICE_HOURS_FORM"
)  # Google Form for office hours

config = {
    "apiKey": firebase_api_key,
    "authDomain": tars_fb_ad,
    "databaseURL": tars_fb_url,
    "storageBucket": tars_fb_sb,
}

firebase = pyrebase.initialize_app(config)
db = firebase.database()

app = App(
    token=tars_token,
    signing_secret=tars_secret,
)

flask_app = Flask(__name__)
flask_app.secret_key = secret
handler = SlackRequestHandler(app)

login_manager = flask_login.LoginManager()
login_manager.init_app(flask_app)
login_manager.login_view = "login"


class User(flask_login.UserMixin):
    pass


@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)


@login_manager.user_loader
def load_user(id):
    if id != username:
        return
    user = User()
    user.id = id
    return user


@flask_app.route("/", methods=["GET"])
def index():
    return redirect("https://solarillionfoundation.org/")


@flask_app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        data1 = {}
        data1["status"] = "Enter credentials."
        return render_template("login.html", data=data1)
    if request.method == "POST":
        username_form = request.form.get("username")
        password_form = request.form.get("password").encode()
        print("Password: %s\tPass Form: %s" % (password, password_form))
        if username_form == username and bcrypt.checkpw(password_form, password):
            user = User()
            user.id = username
            flask_login.login_user(user)
            data1 = {}
            data1["status"] = "Enter the details and submit."
            print("Validated user")
            return redirect(request.args.get("next") or url_for("index"))
        else:
            data1 = {}
            data1["status"] = "Incorrect credentials."
            print("Invalid user")
            return render_template("login.html", data=data1)


@flask_app.route("/logout")
@flask_login.login_required
def logout():
    flask_login.logout_user()
    return redirect(url_for("login"))


@flask_app.route("/interact", methods=["POST"])
def interact():
    payload = json.loads(request.form.get("payload"))
    thread = threading.Thread(
        target=interact_handler,
        args=(
            app,
            db,
            key_fb_tars,
            payload,
        ),
    )
    thread.start()
    return "OK", 200


@app.event("app_mention")
def app_mention_function(event, say):
    thread = threading.Thread(
        target=app_mention_event_handler,
        args=(
            app,
            db,
            key_fb_tars,
            event,
        ),
    )
    thread.start()
    return "OK", 200


@app.message("request office hours")
def request_office_hours(message, say):
    admin = list(db.child(key_fb_tars).child("admin").get().val())
    if message["user"] not in admin:
        say("You're not allowed to do this!")
        return
    msg = "Sir, please fill your office hours in this form: " + office_hours_form_url
    app.client.chat_postMessage(channel=vineethv_id, text=msg)
    logging.info("Sent request to Sir!")


@app.message("remind office hours")
def remind_office_hours(message, say):
    admin = list(db.child(key_fb_tars).child("admin").get().val())

    if message["user"] not in admin:
        say("You're not allowed to do this!")
        return

    msg = (
        "Sir, if you haven't filled your office hours yet, please do so by 9 pm tonight. Here's the link to the form: "
        + office_hours_form_url
    )

    app.client.chat_postMessage(channel=vineethv_id, text=msg)
    logging.info("Sent reminder to Sir!")


@app.message("post office hours")
def post_office_hours(message, say):
    admin = list(db.child(key_fb_tars).child("admin").get().val())
    if message["user"] not in admin:
        say("You're not allowed to do this!")
        return
    data = db.child(key_fb_tars).child("officehours").get().val()
    message = "Sir's office hours for the week:\n"
    for item in data[1:]:
        item["start"] = reformat_time(item["start"])
        item["end"] = reformat_time(item["end"])
        message += item["days"] + ": " + item["start"] + " - " + item["end"] + "\n"
    app.client.chat_postMessage(channel=general, text=message)


@app.message("book meeting")
def book_meeting(message, say):
    slack_id = message["user"]
    meetings = db.child(key_fb_tars).child("meetings").get().val()
    id = "0"
    if meetings is not None:
        for i in list(meetings):
            if slack_id in i:
                id = i
    if id == "0":
        id = slack_id + "_1"
    else:
        id = slack_id + "_" + str(int(id.split("_")[1]) + 1)
    lines = message["text"].lower().split("\n")
    meeting_description = " ".join(lines[0].split(" ")[2:])
    people = [app.client.users_info(user=slack_id).data["user"]["profile"]["email"]]
    people = people + [vineeth_emailid]
    people_slack = [slack_id, vineethv_id]
    if len(lines) == 2:
        attendees = (
            lines[1].replace("@", "").replace("<", "").replace(">", "").upper().split()
        )
        people_slack += attendees
        attendees = list(
            map(
                lambda x: app.client.users_info(user=x).data["user"]["profile"][
                    "email"
                ],
                attendees,
            )
        )
        people = people + attendees
        db.child(key_fb_tars).child("bookings").child(id).set(
            {
                "meeting": meeting_description,
                "people": people,
                "people_slack": people_slack,
            }
        )
    say("The meeting has been booked!")


@app.message("show meeting")
def show_meeting(message, say):
    slack_id = message["user"]
    meetings = db.child(key_fb_tars).child("meetings").get().val()
    if meetings is not None:
        meetings = dict(meetings)
        count = 0
        meet_keys = list(meetings.keys())
        for meet in meet_keys:
            if slack_id in meet:
                count += 1
                item = db.child(key_fb_tars).child("meetings").child(meet).get().val()
                meeting_info = f'{meet.split("_")[1]}. {item["desc"]}, {meet_reformat_time(item["start"])}-{meet_reformat_time(item["end"])}\n Meet Link : {item["meet_link"]}\n'
                if count == 1:
                    say("*Meetings you've booked:*")
                say(meeting_info)
                meetings.pop(meet)
        invites = 0
        meet_keys = list(meetings.keys())
        for meet in meet_keys:
            if slack_id in meetings[meet]["people"]:
                invites += 1
                item = db.child(key_fb_tars).child("meetings").child(meet).get().val()
                meeting_info = f'{meet.split("_")[1]}. {item["desc"]}, {meet_reformat_time(item["start"])}-{meet_reformat_time(item["end"])}\n Meet Link : {item["meet_link"]}\n'
                if invites == 1:
                    say("*Meetings you've been invited to:*")
                say(meeting_info)
                meetings.pop(meet)
        if count == 0 and invites == 0:
            say("You have no upcoming meetings!")
    else:
        say("You haven't booked any meetings this week!")


@app.message("cancel meeting")
def cancel_meeting(message, say):
    slack_id = message["user"]
    meetings = db.child(key_fb_tars).child("meetings").get().val()
    if meetings is None:
        say("You haven't booked any meetings!")
        return
    id = message["text"].lower().split(" ")[2]
    cancel = False
    for meet in meetings:
        if slack_id in meet and meet.split("_")[1] == id:
            db.child(key_fb_tars).child("cancels").update({meet: "cancel"})
            say(f"Meeting with ID {id} has been cancelled!")
            cancel = True
            break
    if not cancel:
        say(
            "Sorry! You've entered the incorrect meeting ID. Verify the meeting number using `show meeting`."
        )


@app.message("update app home")
def update_app_home(message, say):
    users = app.client.users_list().data["members"]
    users = [user["id"] for user in users]
    admin = list(db.child(key_fb_tars).child("admin").get().val())
    ta = list(db.child(key_fb_tars).child("ta").get().val())
    if message["user"] not in ta:
        app.client.chat_postEphemeral(channel=message["channel"], text="Sorry you are not allowed to do this")
    for user in users:
        if user in admin:
            app.client.views_publish(
                user_id=user,
                view={
                    "type": "home",
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "Hi 👋 I'm TARS. I help people at SF do just about everything. Here are a few things that I do:",
                            },
                        },
                        {
                            "type": "section",
                            "fields": [
                                {
                                    "type": "plain_text",
                                    "text": "🤖 Sending notifications and information.",
                                },
                                {"type": "plain_text", "text": "🤖 Booking meetings."},
                                {
                                    "type": "plain_text",
                                    "text": "🤖 Scheduling and posting Sir's office hours and TA hours.",
                                },
                                {
                                    "type": "plain_text",
                                    "text": "🤖 Updating JupyterHub and server SSH links.",
                                },
                                {
                                    "type": "plain_text",
                                    "text": "🤖 Creating and managing polls.",
                                },
                                {
                                    "type": "plain_text",
                                    "text": "🤖 Helping TAs do their job.",
                                },
                            ],
                        },
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": "And a whole lot more."},
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "*Office Hours*\nSir is sent the office hours request automatically every Saturday evening. They are posted every Sunday evening. If the server is down, use `request office hours` to request hours, `remind office hours` to remind Sir, and `post office hours` to post the hours.",
                            },
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "*TA Hours*\nWith the server's help, I request TAs to mark their hours for the upcoming week on Saturday. The hours for Mon-Thu are posted at 6 pm on Sunday, and the hours for Fri-Sun are posted at 6 pm on Thursday. If the server is down, use `request ta hours` to post the polls, `remind weekday ta hours` and `remind weekend ta hours` to send reminders, and `post weekday ta hours` and `post weekend ta hours` to post the hours.",
                            },
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "*Meetings*\nBook meetings with Sir with my help. Check the week's office hours before you book a meeting. You can also view meetings you booked and cancel them. The functions are:",
                            },
                        },
                        {
                            "type": "section",
                            "fields": [
                                {
                                    "type": "mrkdwn",
                                    "text": ":point_right: `book meeting MEETING_TITLE DAY_OF_WEEK TIME DURATION`\n:arrow_right:`@PERSON_1 @PERSON_2 ...`\nExample: `book meeting Paper Review on Friday at 7pm for 15 minutes`\n`@TEAMMATE1 @TEAMMATE2`",
                                },
                                {
                                    "type": "mrkdwn",
                                    "text": ":exclamation: This works with simple, natural language. You can enter `minutes` or `mins`, enter a date or a day or even something like `tomorrow`. The default duration is `15 minutes`. Press `enter` or `return` after typing the meeting details to add participants, in a new line. You are added as a participant by default, so you needn't add yourself. Do not add Sir as a participant, he is also added automatically. You may choose to not add any additional participants at all.",
                                },
                                {
                                    "type": "mrkdwn",
                                    "text": ":point_right: `show meetings`",
                                },
                                {
                                    "type": "mrkdwn",
                                    "text": ":exclamation: This shows the meetings that you have booked or have been invited to this week.",
                                },
                                {
                                    "type": "mrkdwn",
                                    "text": ":point_right: `cancel meeting MEETING_NUMBER`\nExample: `cancel meeting 1`",
                                },
                                {
                                    "type": "mrkdwn",
                                    "text": ":exclamation: Use `show meetings` to list the meetings you've booked and get the `MEETING_NUMBER`. Cancel the meeting using that number. You can only cancel meetings that you booked.",
                                },
                            ],
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": '*Polls*\nPolls can be created in all channels I\'ve been added to by mentioning me. Use `@TARS poll "Question" "Option 1" "Option 2" ...` and include upto `10` options. Tap on an option to select it, and tap on it again to deselect it. The creator of the poll can close or delete the poll as well.',
                            },
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "*TA Orientee Tracking*\nAll TAs and Sir can add or remove orientees from the SF orientee database, track their progress and verify assignments. The functions are:",
                            },
                        },
                        {
                            "type": "section",
                            "fields": [
                                {
                                    "type": "mrkdwn",
                                    "text": ":point_right: `add orientee @SLACK_ID GITHUB GROUP PYTHON_DURATION`\nExample: `add orientee @FakeOrientee fake_orientee ML 7`\nNote that PYTHON_DURATION must be `7` or `10` or `14`. Group duration is set to `14` by default while project duration is `2 months`.",
                                },
                                {
                                    "type": "mrkdwn",
                                    "text": ":point_right: `remove orientee @SLACK_ID`\nExample: `remove orientee @FakeOrientee`",
                                },
                                {
                                    "type": "mrkdwn",
                                    "text": ":point_right: `show orientee @SLACK_ID`\nExample: `show orientee @FakeOrientee`",
                                },
                                {
                                    "type": "mrkdwn",
                                    "text": ":point_right: `verify orientee @SLACK_ID`\nExample: `verify orientee @FakeOrientee`",
                                },
                                {
                                    "type": "mrkdwn",
                                    "text": ":point_right: `track all orientees` or `track all orientees sf_ta`",
                                },
                            ],
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "*Getting the credentials for google and github accounts*\nAll TAs can obtain the credentials for:",
                            },
                        },
                        {
                            "type": "section",
                            "fields": [
                                {
                                    "type": "mrkdwn",
                                    "text": ":one: TA google & github account using `@TARS get TA creds`"
                                },
                                {
                                    "type": "mrkdwn",
                                    "text": ":two: RA google & github account using `@TARS get RA creds`"
                                },
                                {
                                    "type": "mrkdwn",
                                    "text": ":three: all credentials `@TARS get all creds`"
                                }
                                
                            ],
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "plain_text",
                                "text": "Well, that's it for now, but I'll be doing a lot more in the future. Use my services well. Oh, and contact the server team if you have any feature requests or need help. *flashes cue light*",
                            },
                        },
                    ],
                },
            )
        elif user in ta:
            app.client.views_publish(user_id=user, view={
                "type": "home",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Hi 👋 I'm TARS. I help people at SF do just about everything. Here are a few things that I do:"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "plain_text",
                                "text": "🤖 Sending notifications and information."
                            },
                            {
                                "type": "plain_text",
                                "text": "🤖 Booking meetings."
                            },
                            {
                                "type": "plain_text",
                                "text": "🤖 Scheduling and posting Sir's office hours and TA hours."
                            },
                            {
                                "type": "plain_text",
                                "text": "🤖 Updating JupyterHub and server SSH links."
                            },
                            {
                                "type": "plain_text",
                                "text": "🤖 Creating and managing polls."
                            },
                            {
                                "type": "plain_text",
                                "text": "🤖 Helping TAs do their job."
                            }
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "And a whole lot more."
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Office Hours*\nSir is sent the office hours request automatically every Saturday evening. They are posted every Sunday evening. If the server is down, the server admins take over and request or post the office hours."
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*TA Hours*\nWith the server's help, I request TAs to mark their hours for the upcoming week on Saturday. The hours for Mon-Thu are posted at 6 pm on Sunday, and the hours for Fri-Sun are posted at 6 pm on Thursday. If the server is down, the server admins take over and request or post the hours."
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Meetings*\nBook meetings with Sir with my help. Check the week's office hours before you book a meeting. You can also view meetings you booked and cancel them. The functions are:"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": ":point_right: `book meeting MEETING_TITLE DAY_OF_WEEK TIME DURATION`\n:arrow_right:`@PERSON_1 @PERSON_2 ...`\nExample: `book meeting Paper Review on Friday at 7pm for 15 minutes`\n`@TEAMMATE1 @TEAMMATE2`"
                            },
                            {
                                "type": "mrkdwn",
                                "text": ":exclamation: This works with simple, natural language. You can enter `minutes` or `mins`, enter a date or a day or even something like `tomorrow`. The default duration is `15 minutes`. Press `enter` or `return` after typing the meeting details to add participants, in a new line. You are added as a participant by default, so you needn't add yourself. Do not add Sir as a participant, he is also added automatically. You may choose to not add any additional participants at all."
                            },
                            {
                                "type": "mrkdwn",
                                "text": ":point_right: `show meetings`"
                            },
                            {
                                "type": "mrkdwn",
                                "text": ":exclamation: This shows only the meetings that you have booked or have been invited to this week."
                            },
                            {
                                "type": "mrkdwn",
                                "text": ":point_right: `cancel meeting MEETING_NUMBER`\nExample: `cancel meeting 1`"
                            },
                            {
                                "type": "mrkdwn",
                                "text": ":exclamation: Use `show meetings` to list the meetings you've booked and get the `MEETING_NUMBER`. Cancel the meeting using that number. You can only cancel meetings that you have booked."
                            }
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Polls*\nPolls can be created in all channels I've been added to by mentioning me. Use `@TARS poll \"Question\" \"Option 1\" \"Option 2\" ...` and include upto `10` options. Tap on an option to select it, and tap on it again to deselect it. The creator of the poll can close or delete the poll as well."
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*TA Orientee Tracking*\nAll TAs and Sir can add or remove orientees from the SF orientee database, track their progress and verify assignments. The functions are:"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": ":point_right: `add orientee @SLACK_ID GITHUB GROUP PYTHON_DURATION`\nExample: `add orientee @FakeOrientee fake_orientee ML 7`\nNote that PYTHON_DURATION must be `7` or `10` or `14`. Group duration is set to `14` by default while project duration is `2 months`."
                            },
                            {
                                "type": "mrkdwn",
                                "text": ":point_right: `remove orientee @SLACK_ID`\nExample: `remove orientee @FakeOrientee`"
                            },
                            {
                                "type": "mrkdwn",
                                "text": ":point_right: `show orientee @SLACK_ID`\nExample: `show orientee @FakeOrientee`"
                            },
                            {
                                "type": "mrkdwn",
                                "text": ":point_right: `verify orientee @SLACK_ID`\nExample: `verify orientee @FakeOrientee`"
                            },
                            {
                                "type": "mrkdwn",
                                "text": ":point_right: `track all orientees` or `track all orientees sf_ta`"
                            }
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Getting the credentials for google and github accounts*\nAll TAs can obtain the credentials for:",
                        },
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": ":one: TA google & github account using `@TARS get TA creds`"
                            },
                            {
                                "type": "mrkdwn",
                                "text": ":two: RA google & github account using `@TARS get RA creds`"
                            },
                            {
                                "type": "mrkdwn",
                                "text": ":three: all credentials `@TARS get all creds`"
                            }
                            
                        ],
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "plain_text",
                            "text": "Well, that's it for now, but I'll be doing a lot more in the future. Use my services well. Oh, and contact the server team if you have any feature requests or need help. *flashes cue light*"
                        }
                    }
                ]
            },)
        else:
            app.client.views_publish(user_id=user, view={
                "type": "home",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Hi 👋 I'm TARS. I help people at SF do just about everything. Here are a few things that I do:"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "plain_text",
                                "text": "🤖 Sending notifications and information."
                            },
                            {
                                "type": "plain_text",
                                "text": "🤖 Scheduling and posting Sir's office hours and TA hours."
                            },
                            {
                                "type": "plain_text",
                                "text": "🤖 Updating JupyterHub and server SSH links."
                            },
                            {
                                "type": "plain_text",
                                "text": "🤖 Booking meetings."
                            },
                            {
                                "type": "plain_text",
                                "text": "🤖 Creating and managing polls."
                            },
                            {
                                "type": "plain_text",
                                "text": "🤖 Helping TAs do their job."
                            }
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "And a whole lot more."
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Office Hours*\nSir is sent the office hours request automatically every Saturday evening. They are posted every Sunday evening. If the server is down, the server admins take over and request or post the office hours."
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*TA Hours*\nWith the server's help, I request TAs to mark their hours for the upcoming week on Saturday. The hours for Mon-Thu are posted at 6 pm on Sunday, and the hours for Fri-Sun are posted at 6 pm on Thursday. If the server is down, the server admins take over and request or post the hours."
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Meetings*\nBook meetings with Sir with my help. Check the week's office hours before you book a meeting. You can also view meetings you booked and cancel them. The functions are:"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": ":point_right: `book meeting MEETING_TITLE DAY_OF_WEEK TIME DURATION`\n:arrow_right:`@PERSON_1 @PERSON_2 ...`\nExample: `book meeting Paper Review on Friday at 7pm for 15 minutes`\n`@TEAMMATE1 @TEAMMATE2`"
                            },
                            {
                                "type": "mrkdwn",
                                "text": ":exclamation: This works with simple, natural language. You can enter `minutes` or `mins`, enter a date or a day or even something like `tomorrow`. The default duration is `15 minutes`. Press `enter` or `return` after typing the meeting details to add participants, in a new line. You are added as a participant by default, so you needn't add yourself. Do not add Sir as a participant, he is also added automatically. You may choose to not add any additional participants at all."
                            },
                            {
                                "type": "mrkdwn",
                                "text": ":point_right: `show meetings`"
                            },
                            {
                                "type": "mrkdwn",
                                "text": ":exclamation: This shows only the meetings that you have booked or have been invited to this week."
                            },
                            {
                                "type": "mrkdwn",
                                "text": ":point_right: `cancel meeting MEETING_NUMBER`\nExample: `cancel meeting 1`"
                            },
                            {
                                "type": "mrkdwn",
                                "text": ":exclamation: Use `show meetings` to list the meetings you've booked and get the `MEETING_NUMBER`. Cancel the meeting using that number. You can only cancel meetings that you booked."
                            }
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Polls*\nPolls can be created in all channels I've been added to by mentioning me. Use `@TARS poll \"Question\" \"Option 1\" \"Option 2\" ...` and include upto `10` options. Tap on an option to select it, and tap on it again to deselect it. The creator of the poll can close or delete the poll as well."
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Getting the credentials for google and github accounts*\nAll TAs can obtain the credentials for:",
                        },
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": ":one: RA google & github account using `@TARS get RA creds`"
                            },
                        ],
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "plain_text",
                            "text": "Well, that's it for now, but I'll be doing a lot more in the future. Use my services well. Oh, and contact the server team if you have any feature requests or need help. *flashes cue light*­"
                        }
                    }
                ]
            })


@app.event("message")
def handle_message_events(body):
    logging.info(body)


if __name__ == "__main__":
    flask_app.run(port=5000)
