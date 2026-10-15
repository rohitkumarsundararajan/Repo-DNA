from flask import Flask

app = Flask(__name__)


def normalize_name(name):
    return name.strip().lower()


def classify_score(score):
    if score < 0:
        return "negative"
    return "non-negative"
