import os
from flask import Flask, render_template, request, jsonify
from suds.client import Client
from suds.cache import NoCache
import json
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# API Credentials (Read from Environment Variables)
USERNAME = os.getenv("API_USERNAME")
PASSWORD = os.getenv("API_PASSWORD")
LANGUAGE = 'EN'
PACKAGE_REC_NO = 21
ACTION = 'IssueQuotation'

# Initialize SOAP Client
WSDL_URL = 'https://test.cosmosins.com/CosmosOnlineService.asmx?WSDL'
client = Client(WSDL_URL, cache=NoCache())


def call_api(method_name, params):
    """
    Generic function to call the SOAP API with a given method name and parameters.
    """
    try:
        method_to_execute = getattr(client.service, method_name)
        response = method_to_execute(*params)

        # Print raw response for debugging
        print(f"API Response ({method_name}):", response)

        # Convert response to JSON if needed
        if isinstance(response, str):
            response_data = json.loads(response)
        else:
            response_data = response  # Already a dictionary

        return response_data

    except Exception as e:
        print(f"Error calling {method_name}: {str(e)}")
        return {}


def get_field_options(field_name, field_param=""):
    """
    Fetches available values for a given dropdown field.
    """
    field_params = f'{{"Parameters":[{{"Parameter":"{field_param}"}}]}}' if field_param else ""

    params = [USERNAME, PASSWORD, LANGUAGE, PACKAGE_REC_NO, ACTION, field_name, field_params]
    response_data = call_api("GetFieldAvailableValues", params)

    # Extract "Options" if available, otherwise return empty list
    options = response_data.get("Options", [])
    formatted_options = [(opt["Code"], opt["Description"]) for opt in options]  # Extract Code and Description

    return formatted_options  # Returns a list of (Code, Description) tuples


@app.route('/', methods=['GET', 'POST'])
def form():
    params = [USERNAME, PASSWORD, LANGUAGE, PACKAGE_REC_NO, ACTION]
    response_data = call_api("GetPackageDefinitionAllFields", params)

    fields = response_data.get("Fields", [])

    # Group fields by GroupCaption
    grouped_fields = defaultdict(list)
    dropdown_options = {}
    form_values = request.form.to_dict() if request.method == 'POST' else {}

    for field in fields:
        group_caption = field.get("GroupCaption", "Other")  # Default to 'Other' if no GroupCaption
        grouped_fields[group_caption].append(field)

        # Fetch dropdown options dynamically
        if field["Type"] == "DROPDOWN":
            field_param = form_values.get(field["FieldName"], "")
            dropdown_options[field["FieldName"]] = get_field_options(field["FieldName"], field_param)

    return render_template(
        'form.html',
        grouped_fields=grouped_fields,
        dropdown_options=dropdown_options,
        form_values=form_values
    )


@app.route('/update_form', methods=['POST'])
def update_form():
    updated_field = request.json.get("field_name")
    updated_value = request.json.get("field_value")
    current_values = request.json.get("form_values", {})

    params = [USERNAME, PASSWORD, LANGUAGE, PACKAGE_REC_NO, ACTION]
    response_data = call_api("GetPackageDefinitionAllFields", params)

    fields = response_data.get("Fields", [])
    grouped_fields = defaultdict(list)
    dropdown_options = {}

    for field in fields:
        group_caption = field.get("GroupCaption", "Other")
        grouped_fields[group_caption].append(field)

        # Fetch dropdown options dynamically based on updated field value
        if field["Type"] == "DROPDOWN":
            field_param = current_values.get(field["FieldName"], "")
            dropdown_options[field["FieldName"]] = get_field_options(field["FieldName"], field_param)

    return jsonify({
        "html": render_template(
            'form_fields.html',
            grouped_fields=grouped_fields,
            dropdown_options=dropdown_options,
            form_values=current_values
        )
    })


if __name__ == '__main__':
    app.run(debug=True)
