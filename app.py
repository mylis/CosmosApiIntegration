import os
from flask import Flask, render_template, request, jsonify, redirect, url_for
from suds.client import Client
from suds.cache import NoCache
import json
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# API Credentials
USERNAME = os.getenv("API_USERNAME")
PASSWORD = os.getenv("API_PASSWORD")
LANGUAGE = 'GR'
ACTION = 'IssueQuotation'

# SOAP Client
WSDL_URL = 'https://test.cosmosins.com/CosmosOnlineService.asmx?WSDL'
client = Client(WSDL_URL, cache=NoCache())


def call_api(method_name, params):
    """ Generic function to call SOAP API methods. """
    try:
        method_to_execute = getattr(client.service, method_name)
        response = method_to_execute(*params)
        print(f"API Response ({method_name}):", response)  # Debugging
        return json.loads(response) if isinstance(response, str) else response
    except Exception as e:
        print(f"Error calling {method_name}: {str(e)}")
        return {}

def get_field_options(record_id, field_name, data_type="quotation"):
    """
    Fetches available values for a given dropdown field.

    :param record_id: Quotation ID or Proposal ID
    :param field_name: Name of the field to fetch values for
    :param data_type: "quotation" or "proposal"
    :return: List of (Code, Description) tuples
    """

    field_value_methods = {
        "quotation": "GetQuotationFieldAvailableValues",
        "proposal": "GetProposalFieldAvailableValues",
    }

    if data_type not in field_value_methods:
        raise ValueError("Invalid data_type. Must be 'quotation' or 'proposal'.")

    method_name = field_value_methods[data_type]
    params = [USERNAME, PASSWORD, LANGUAGE, int(record_id), field_name]

    response_data = call_api(method_name, params)
    options = response_data.get("Options", [])

    return [(opt["Code"], opt["Description"]) for opt in options]  # Extract Code and Description


def fetch_fields(record_id, data_type, all_fields=False, fetch_available_values=False):
    """
    Fetches fields based on the data type and whether to return all fields or only required ones.

    :param record_id: ID of the package, quotation, or proposal.
    :param data_type: One of "packagedefinition", "quotation", or "proposal".
    :param all_fields: Boolean - whether to return all fields or only required ones.
    :param fetch_available_values: Boolean - whether to fetch field available values.
    :return: grouped_fields, dropdown_options
    """

    api_methods = {
        "packagedefinition": "GetPackageDefinitionAllFields" if all_fields else "GetPackageDefinition",
        "quotation": "GetQuotationAllFields" if all_fields else "GetQuotationFields",
        "proposal": "GetProposalAllFields" if all_fields else "GetProposalFields",
    }

    if data_type not in api_methods:
        raise ValueError("Invalid data_type. Must be 'packagedefinition', 'quotation', or 'proposal'.")

    method_name = api_methods[data_type]
    params = [USERNAME, PASSWORD, LANGUAGE, int(record_id)]

    fields_response = call_api(method_name, params)
    fields = fields_response.get("Fields", [])

    grouped_fields = defaultdict(list)
    dropdown_options = {}

    for field in fields:
        group_caption = field.get("GroupCaption", "Other")
        grouped_fields[group_caption].append(field)

        # Fetch dropdown values dynamically
        if fetch_available_values and field["Type"] == "DROPDOWN":
            dropdown_options[field["FieldName"]] = get_field_options(record_id, field["FieldName"], data_type)

    return grouped_fields, dropdown_options


@app.route('/')
def package_list():
    """ Fetch and display insurance packages.html. """
    params = [USERNAME, PASSWORD, LANGUAGE, ACTION]
    response_data = call_api("GetPackageList", params)

    packages = response_data.get("Packages", [])
    return render_template('packages.html', packages=packages)


@app.route('/quotation', methods=['GET', 'POST'])
def quotation():
    """
    Fetches a new or existing quotation and retrieves its fields.
    """
    package_rec_no = request.args.get("package_rec_no")
    quotation_number = request.args.get("quotation_number")

    grouped_fields, dropdown_options = defaultdict(list), {}
    form_values = request.form.to_dict() if request.method == 'POST' else {}  # Ensure form_values is initialized

    if package_rec_no:
        # Create a new quotation
        params = [USERNAME, PASSWORD, LANGUAGE, int(package_rec_no), '{"Fields":[]}']
        response_data = call_api("GetQuote", params)
        quotation_number = response_data.get("Quotation Number")

    if quotation_number:
        # Fetch fields for quotation and available dropdown values
        grouped_fields, dropdown_options = fetch_fields(
            quotation_number, "quotation", all_fields=True, fetch_available_values=True
        )

    return render_template(
        'quotation.html',
        quotation_number=quotation_number,
        grouped_fields=grouped_fields,
        dropdown_options=dropdown_options,
        form_values=form_values,
        package_rec_no=package_rec_no
    )

@app.route('/update_quote', methods=['POST'])
def update_quote():
    """
    Updates the quotation when a field with 'AffectsOtherFields' is changed or when the form is submitted.
    """
    quotation_number = request.json.get("quotation_number")
    updated_fields = request.json.get("updated_fields", {})

    if not quotation_number:
        return jsonify({"error": "Quotation number is required"}), 400

    # Construct QuotationJson from updated fields
    quotation_json = {
        "Fields": [
            {
                "FieldName": key,
                "FieldType": "UNKNOWN",  # FieldType can be dynamically assigned if needed
                "FieldValue": value
            }
            for key, value in updated_fields.items()
        ]
    }

    # Call UpdateQuote API
    params = [USERNAME, PASSWORD, LANGUAGE, int(quotation_number), json.dumps(quotation_json)]
    response_data = call_api("UpdateQuote", params)

    # Fetch latest quotation fields
    grouped_fields, dropdown_options = fetch_fields(
        quotation_number, "quotation", all_fields=True, fetch_available_values=True
    )

    return jsonify({
        "html": render_template(
            "form_fields.html",
            grouped_fields=grouped_fields,
            dropdown_options=dropdown_options,
            form_values=updated_fields
        ),
        "quotation_number": quotation_number
    })


if __name__ == '__main__':
    app.run(debug=True)
