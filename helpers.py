from datetime import *
from poll import handle_poll
import os

TA_GITHUB_UNAME = os.environ.get("TA_GITHUB_UNAME", "Err TA_GITHUB_UNAME")
TA_GITHUB_PW = os.environ.get("TA_GITHUB_PW", "Err TA_GITHUB_PW")

TA_GOOGLE_UNAME = os.environ.get("TA_GOOGLE_UNAME", "Err TA_GOOGLE_UNAME")
TA_GOOGLE_PW = os.environ.get("TA_GOOGLE_PW", "Err TA_GOOGLE_PW")

RA_GOOGLE_UNAME = os.environ.get("RA_GOOGLE_UNAME", "Err RA_GOOGLE_UNAME")
RA_GOOGLE_PW = os.environ.get("RA_GOOGLE_PW", "Err RA_GOOGLE_PW")


def reformat_time(ts):
    t = datetime.strptime(ts[11:19], "%H:%M:%S").time()
    t = datetime.combine(date.today(), t) + timedelta(hours=5, minutes=21, seconds=10)
    return t.strftime("%I:%M %p")


def meet_reformat_time(ts):
    t = datetime.strptime(ts[11:19], "%H:%M:%S").time()
    t = datetime.combine(date.today(), t)
    return t.strftime("%I:%M %p")


def get_credentials(app, db, key_fb_tars, event_data, type="RA"):
    user = event_data["user"]
    ta_list = db.child(key_fb_tars).child("ta").get().val()
    # ra_list = db.child(key_fb_tars).child("ra").get().val()
    if type == "TA" or type == "ALL":
        if user not in ta_list:
            app.client.chat_postEphemeral(
                channel=event_data["channel"],
                text="Sorry! You are not allowed to do this!",
            )
        else:
            ta_google = (
                "*Credentials for TA google account:*\n"
                + "Username: "
                + TA_GOOGLE_UNAME
                + "\nPassword: "
                + TA_GOOGLE_PW
            )
            ta_github = (
                "*Credentials for TA github account:*\n"
                + "Username: "
                + TA_GITHUB_UNAME
                + "\nPassword: "
                + TA_GITHUB_PW
            )
            ta_creds_message = ta_google + "\n" + ta_github
            app.client.chat_postMessage(channel=user, text=ta_creds_message)
    if type == "RA" or type == 'ALL':
        ra_google = (
            "*Credentials for RA google account:*\n"
            + "Username: "
            + RA_GOOGLE_UNAME
            + "\nPassword: "
            + RA_GOOGLE_PW
        )
        ra_creds_message = ra_google  # add RA github if requried.
        app.client.chat_postMessage(channel=user, text=ra_creds_message)
    

def app_mention_event_handler(app, db, key_fb_tars, event_data):
    text = event_data["text"]
    if "ping" in text.lower():
        app.client.chat_postMessage(channel=event_data["user"], text="Hello!")
    elif "poll" in text.lower():
        handle_poll(app, db, key_fb_tars, event_data)
    elif "get ra creds" in text.lower():
        get_credentials(app, db, key_fb_tars, event_data, "RA")
    elif "get ta creds" in text.lower():
        get_credentials(app, db, key_fb_tars, event_data, "TA")
    elif "get all creds" in text.lower():
        get_credentials(app, db, key_fb_tars, event_data, "ALL")
    else:
        pass


def interact_handler(app, db, key_fb_tars, payload):
    user = payload["user"]["id"]
    channel = payload["container"]["channel_id"]
    ts = payload["message"]["ts"]
    value = payload["actions"][0]["value"]
    question = (
        db.child(key_fb_tars)
        .child("polls")
        .child(ts.replace(".", "-"))
        .child("question")
        .get()
        .val()
    )
    if value == "delete_poll":
        if (
            db.child(key_fb_tars)
            .child("polls")
            .child(ts.replace(".", "-"))
            .child("user")
            .get()
            .val()
            == user
        ):
            app.client.chat_update(
                channel=channel,
                ts=ts,
                text="Poll " + question + " deleted!",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Poll " + question + " deleted!",
                        },
                    }
                ],
            )
            db.child(key_fb_tars).child("polls").child(ts.replace(".", "-")).remove()
        else:
            app.client.chat_postEphemeral(
                channel=channel,
                user=user,
                text="You can only delete polls that you create.",
            )
    elif value == "end_poll":
        if (
            db.child(key_fb_tars)
            .child("polls")
            .child(ts.replace(".", "-"))
            .child("user")
            .get()
            .val()
            == user
        ):
            app.client.chat_update(
                channel=channel,
                ts=ts,
                text="Poll " + question + " closed!",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Poll " + question + " closed!",
                        },
                    }
                ],
            )
            poll = (
                db.child(key_fb_tars)
                .child("polls")
                .child(ts.replace(".", "-"))
                .get()
                .val()
            )
            db.child(key_fb_tars).child("polls").child(ts.replace(".", "-")).remove()
            app.client.chat_postMessage(channel=channel, text="*Poll Results*")
            for block in poll["message"][1:-3]:
                text = block["text"]["text"]
                app.client.chat_postMessage(channel=channel, text=text)
        else:
            app.client.chat_postEphemeral(
                channel=channel,
                user=user,
                text="You can only close polls that you create.",
            )
    elif "_poll" in value:
        emoji = [
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "keycap_ten",
        ]
        value = value.split("_")[0]
        index = emoji.index(value) + 1
        poll = (
            db.child(key_fb_tars).child("polls").child(ts.replace(".", "-")).get().val()
        )
        votes = (
            db.child(key_fb_tars)
            .child("polls")
            .child(ts.replace(".", "-"))
            .child("votes")
            .child(str(index))
            .get()
            .val()
        )
        if votes is None:
            db.child(key_fb_tars).child("polls").child(ts.replace(".", "-")).child(
                "votes"
            ).child(str(index)).update({0: user})
            current = (
                db.child(key_fb_tars)
                .child("polls")
                .child(ts.replace(".", "-"))
                .child("message")
                .child(str(index))
                .child("text")
                .child("text")
                .get()
                .val()
            )
            db.child(key_fb_tars).child("polls").child(ts.replace(".", "-")).child(
                "message"
            ).child(str(index)).child("text").update(
                {"text": current.strip() + " `1` ~ <@" + user + ">"}
            )
        else:
            current = (
                db.child(key_fb_tars)
                .child("polls")
                .child(ts.replace(".", "-"))
                .child("message")
                .child(str(index))
                .child("text")
                .child("text")
                .get()
                .val()
            )
            if user not in current:
                i = len(votes)
                db.child(key_fb_tars).child("polls").child(ts.replace(".", "-")).child(
                    "votes"
                ).child(str(index)).update({i: user})
                db.child(key_fb_tars).child("polls").child(ts.replace(".", "-")).child(
                    "message"
                ).child(str(index)).child("text").update(
                    {
                        "text": current.split("`")[0]
                        + "`"
                        + str(i + 1)
                        + "` ~ <@"
                        + user
                        + ">"
                        + current.split("~")[1]
                    }
                )
            else:
                for i in votes:
                    if i == user:
                        votes.remove(i)
                db.child(key_fb_tars).child("polls").child(ts.replace(".", "-")).child(
                    "votes"
                ).child(str(index)).remove()
                j = 0
                for i in votes:
                    db.child(key_fb_tars).child("polls").child(
                        ts.replace(".", "-")
                    ).child("votes").child(str(index)).update({j: i})
                    j += 1
                current = (
                    db.child(key_fb_tars)
                    .child("polls")
                    .child(ts.replace(".", "-"))
                    .child("message")
                    .child(str(index))
                    .child("text")
                    .child("text")
                    .get()
                    .val()
                )
                if j == 0:
                    db.child(key_fb_tars).child("polls").child(
                        ts.replace(".", "-")
                    ).child("message").child(str(index)).child("text").update(
                        {"text": current.split("`")[0]}
                    )
                else:
                    db.child(key_fb_tars).child("polls").child(
                        ts.replace(".", "-")
                    ).child("message").child(str(index)).child("text").update(
                        {
                            "text": current.split("`")[0]
                            + "`"
                            + str(j)
                            + "` ~ "
                            + current.split("~")[1]
                            .replace("<@" + user + ">", "")
                            .strip()
                        }
                    )
        blocks = dict(
            db.child(key_fb_tars).child("polls").child(ts.replace(".", "-")).get().val()
        )["message"]
        app.client.chat_update(channel=channel, ts=ts, blocks=blocks)
