
import os
import openai
import xml.etree.ElementTree as ET
from flask import Flask, request, render_template, jsonify
from flask_cors import CORS  # Import the CORS module

from key import OPENAI_KEY

app = Flask(__name__)
CORS(app)  # Enable CORS for the app
# Define namespaces
namespaces = {
    'default': 'urn:hl7-org:v3',
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
    'sdtc': 'urn:hl7-org:sdtc'
}
openai.api_key = OPENAI_KEY

uploaded_xml_path = None
def extract_section_names(xml_path):
    # Parse the XML file
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Extract section names
    section_names = []
    for section in root.findall(".//default:section", namespaces=namespaces):
        title_element = section.find("default:title", namespaces=namespaces)
        if title_element is not None:
            section_names.append(title_element.text)
    return section_names

def extract_section_data(xml_path, section_name):
    # Parse the XML file
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Search for the section by its title
    for section in root.findall(".//default:section", namespaces=namespaces):
        title_element = section.find("default:title", namespaces=namespaces)
        if title_element is not None and title_element.text == section_name:
            # Convert the section subtree to a formatted XML string
            return ET.tostring(section, encoding="unicode", method="xml")
    return "Section not found"

def xml_to_readable(section_xml):
    section = ET.fromstring(section_xml)

    output = []

    title_element = section.find("default:title", namespaces=namespaces)
    if title_element is not None:
        output.append(title_element.text)
        output.append('-' * len(title_element.text))

    for table in section.findall(".//default:table", namespaces=namespaces):
        headers = [th.text for th in table.findall(".//default:thead/default:tr/default:th", namespaces=namespaces)]
        output.append(' | '.join(headers))
        output.append('-' * (sum([len(header) for header in headers]) + len(headers) * 3 - 2))

        for row in table.findall(".//default:tbody/default:tr", namespaces=namespaces):
            row_data = [td.text if td.text else ' '.join(td.itertext()) for td in
                        row.findall(".//default:td", namespaces=namespaces)]
            output.append(' | '.join(row_data))

        output.append('')

    return '\n'.join(output)

# @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@




@app.route("/", methods=['GET'])
def hello():
    return jsonify("Hello World")

@app.route("/upload", methods=["POST"])
def index():
    global uploaded_xml_path  # Access the global variable
    xml_file = request.files.get("xml_file")

    if xml_file is None:
        return jsonify({"error": "No file uploaded."}), 400

    # Check if the uploaded file is in XML format
    if not xml_file.filename.lower().endswith(".xml"):
        return jsonify({"error": "Uploaded file is not in XML format."}), 400

    print("Inside upload method")
    uploaded_xml_path = os.path.join("files", xml_file.filename)
    xml_file.save(uploaded_xml_path)
    print("Inside upload method file saved")

    return jsonify("XML file uploaded successfully!"), 200

@app.route("/get_section_names", methods=["GET"])
def get_section_names():
    global uploaded_xml_path  # Access the global variable
    if uploaded_xml_path:
        section_names_list = extract_section_names(uploaded_xml_path)
        return jsonify({"section_names": section_names_list})
    else:
        return jsonify({"message": "No uploaded XML file found."})

@app.route("/get_section_data/<section_name>", methods=["GET"])
def get_section_data(section_name):
    print("Inside get_section_data function")
    global uploaded_xml_path  # Access the global variable

    if not uploaded_xml_path:
        return jsonify({"message": "No uploaded XML file found."})

    chosen_section_xml = extract_section_data(uploaded_xml_path, section_name)
    if chosen_section_xml == "Section not found":
        return jsonify({"message": f"Section '{section_name}' not found."})

    readable_output = xml_to_readable(chosen_section_xml)

    # Prompt for summarization
    prompt = f"This is the data for one patient.Give summary of this data in bullet points:\n{readable_output}"

    # Use OpenAI API for summarization
    summary = openai.Completion.create(
        engine="text-davinci-003",  # You can choose a different engine if needed
        prompt=prompt,
        max_tokens=200  # Adjust the number of tokens as needed
    )

    return jsonify({"section_data": readable_output, "summary": summary.choices[0].text.strip()})

def extract_personal_info(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    personal_info = {}

    patient_element = root.find(".//default:patient", namespaces=namespaces)
    if patient_element is not None:
        personal_info["Name"] = patient_element.find(".//default:name/default:given", namespaces=namespaces).text + " " + patient_element.find(".//default:name/default:family", namespaces=namespaces).text
        personal_info["Gender"] = patient_element.find(".//default:administrativeGenderCode", namespaces=namespaces).get("displayName")
        personal_info["Birthdate"] = patient_element.find(".//default:birthTime", namespaces=namespaces).get("value")
        personal_info["Marital Status"] = patient_element.find(".//default:maritalStatusCode", namespaces=namespaces).get("displayName")
        personal_info["Race"] = patient_element.find(".//default:raceCode", namespaces=namespaces).get("displayName")
        personal_info["Language"] = patient_element.find(".//default:languageCommunication/default:languageCode", namespaces=namespaces).get("code")

    return personal_info

@app.route("/extract_personal_details", methods=["GET"])
def extract_personal_details():
    global uploaded_xml_path  # Access the global variable

    if not uploaded_xml_path:
        return jsonify({"message": "No uploaded XML file found."})

    personal_details = extract_personal_info(uploaded_xml_path)

    details_output = "\n".join([f"{key}: {value}" for key, value in personal_details.items()])



    return jsonify({"personal_details": details_output})


@app.route("/extract_medical_data", methods=["GET"])
def extract_medical_data():
    global uploaded_xml_path  # Access the global variable

    if not uploaded_xml_path:
        return jsonify({"message": "No uploaded XML file found."})

    sections_to_extract = ['Notes', 'Problems', 'Allergies', 'Medical History']

    extracted_data = {}

    for section_name in sections_to_extract:
        section_xml = extract_section_data(uploaded_xml_path, section_name)
        if section_xml != "Section not found":
            readable_section = xml_to_readable(section_xml)
            extracted_data[section_name] = readable_section

    summaries = {}

    for section_name, section_content in extracted_data.items():
        # If section content is empty, append a hardcoded message
        if not section_content:
            section_content = "Nothing Reported."

        # Modify prompts to focus on data rather than description
        prompt = ""
        if section_name == "Allergies":
            prompt = f"Summarize the allergies mentioned in the section '{section_name}':\n{section_content}\nInclude details about allergens and reactions."
        elif section_name == "Medical History":
            prompt = f"Summarize the medical conditions with 'yes' responses mentioned in the '{section_name}' section:\n{section_content}"
        else:
            prompt = f"Summarize the data in the section '{section_name}':\n{section_content}Include Dates"

        summary = openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=150
        )

        summaries[section_name] = summary.choices[0].text.strip()

    # Remove unwanted key
    if "is the data for one patient." in summaries:
        del summaries["is the data for one patient."]

    return jsonify(summaries)


def extract_data_from_table_section(section_name, key_header, value_header, root):
    data = []

    # Find the section by its title
    for section in root.findall(".//default:section", namespaces=namespaces):
        title_element = section.find("default:title", namespaces=namespaces)
        if title_element is not None and title_element.text == section_name:

            # Iterate over each table in the section
            for table in section.findall(".//default:table", namespaces=namespaces):
                headers = [th.text.strip() for th in table.findall(".//default:thead/default:tr/default:th", namespaces=namespaces)]

                # Check if the table has the desired key and value headers
                if key_header in headers and value_header in headers:
                    key_index = headers.index(key_header)
                    value_index = headers.index(value_header)

                    # Iterate over each row in the table
                    for row in table.findall(".//default:tbody/default:tr", namespaces=namespaces):
                        row_data = [td.text.strip() if td.text else ' '.join(td.itertext()) for td in row.findall(".//default:td", namespaces=namespaces)]

                        # Extract the key-value pair based on the header indexes
                        key_value = (row_data[key_index], row_data[value_index])
                        data.append(key_value)

    return data

@app.route("/extract_key_value_data", methods=["GET"])
def extract_key_value_data():
    global uploaded_xml_path

    if not uploaded_xml_path:
        return jsonify({"message": "No uploaded XML file found."})

    # Parse the XML file
    tree = ET.parse(uploaded_xml_path)
    root = tree.getroot()

    # Execute the extraction functions for the specified sections and headers
    past_encounters_data_table = extract_data_from_table_section('Past Encounters', 'Encounter date', 'Diagnosis/Indication', root)
    vitals_data_table = extract_data_from_table_section('Vitals', 'Date Recorded', 'Body mass index (BMI)', root)
    procedures_data_table_1 = extract_data_from_table_section('Procedures', 'Date', 'Name', root)
    procedures_data_table_2 = extract_data_from_table_section('Procedures', 'Imaging Date', 'Name', root)
    assessment_data_table = extract_data_from_table_section('Assessment', 'Assessment Date', 'Assessment', root)
    medication_data_table=extract_data_from_table_section('Medications','Name','Status',root)
    # Return the extracted data
    return jsonify({
        "Past Encounters": past_encounters_data_table,
        "Vitals": vitals_data_table,
        "Procedures": procedures_data_table_1,
        "Procedures (Imaging)": procedures_data_table_2,
        "Assessment": assessment_data_table,
        "Medications":medication_data_table
    })

if __name__ == "__main__":
    app.run(debug=True)

