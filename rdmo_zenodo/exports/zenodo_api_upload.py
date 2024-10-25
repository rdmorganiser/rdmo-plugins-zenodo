import requests

token = "token_generated_from_Zenodo_for_RDMO"

API_URL = "https://sandbox.zenodo.org/api/"
URL = "https://sandbox.zenodo.org/"
DOI_URL = "https://doi.org/10.5072/zenodo."
PUBLISHER = "RDMO"

json_header = {
    "Accept": "application/json",
    'Content-Type': 'application/json',
    'Authorization': 'Bearer {}'.format(token)  
}
binary_header= {
    "Accept": "application/json",
    'Content-Type': 'application/octet-stream',
    'Authorization': 'Bearer {}'.format(token) 
}
plain_header = {
    "Accept": "application/json",
    'Authorization': 'Bearer {}'.format(token)  
}

# sample json data
sample_data = {
    "metadata": {
        "title": "RDMO_02",
        "description": "schubidu, schubida",
        "creators": [
            {
                "person_or_org": {
                    "given_name": "Max",
                    "family_name": "Mustermann",
                    "type": "personal",
                    "identifiers": [{"identifier": "0001-0002-0003-0004"}]
                },
                "affiliations": [{"name": "University of Test"}]
            }
        ],
        "publication_date": "2024-10-17",
        "publisher": PUBLISHER,
        "resource_type": {"id": "publication-datamanagementplan"},
        "subjects": [{"subject": "Data Management Plan"}, {"subject": "DMP"}]
    }
}

def convert_json(input_json, publication_date, publisher):
    """
    Convert the metadata output of a Zenodo response into a
    format that gets accepted as input.
    """
    output_json = {}
    output_json['metadata'] = {
        'title': input_json['metadata']['title'],
        'description': input_json['metadata']['description'],
        'publication_date': publication_date,
        'publisher': publisher,
        'creators': [{
            'person_or_org': {
                'given_name': creator['name'].split(', ')[1],
                'family_name': creator['name'].split(', ')[0],
                'type': 'personal',
                'identifiers': [{'identifier': creator['orcid']}]
            },
            'affiliations': [{'name': creator['affiliation']}]
        } for creator in input_json['metadata']['creators']],
        'resource_type': {
            'id': "publication-datamanagementplan"
        },
        'subjects': [{'subject': keyword} for keyword in input_json['metadata']['keywords']]
    }

    return output_json

def upload_file(id, binary=None):
    # POST data / PDF
    files_url = API_URL+f"records/{id}/draft/files"
    file_data = [{"key": "DMP.pdf"}]
    data_initialization_response = requests.post(files_url, headers=json_header, json=file_data)

    # upload the actual file content as binary stream
    files_content_url = API_URL+f"records/{id}/draft/files/{file_data[0]['key']}/content"
    ## multiple files as upload realistic???                         ^^^

    # upload data from a file path
    file_path = r'C:\Users\path\to\my.pdf'

    # Open the file in binary mode
    with open(file_path, 'rb') as file:
        data_content_response = requests.put(files_content_url, headers=binary_header, data=file)

    # alternative with binary data
    #data_content_response = requests.put(files_content_url, headers=binary_header, data=binary)

    # commit the file upload
    file_commit_url = API_URL+f"records/{id}/draft/files/{file_data[0]['key']}/commit"
    data_commit_response = requests.post(file_commit_url, headers=plain_header)

def create_record(metadata):
    records_url = API_URL+"records"
    draft_response = requests.post(records_url, headers=json_header, json=metadata)
    # return the id of the draft
    return draft_response.json()["id"]

def get_publication_url(id):
    return URL+f"uploads/{id}"

def get_doi(id):
    """
    id is the Zenodo record id
    """
    return DOI_URL+f"{id}"

def get_overarching_doi(id_v1):
    """
    we need the id of v1
    overarching id = id of v1 -1
    """
    return DOI_URL+f"{int(id_v1) - 1}"


def create_new_version(id_v1, new_date, publisher=PUBLISHER):
    """
    id of v1 needed, NOT "overall" id!!!
    new_date: e.g. "2024-10-17"
    returns id of the new draft
    """
    new_version_response = requests.post(API_URL+f"records/{id_v1}/versions", headers=plain_header).json()
    new_id = new_version_response["id"]
    # get metadata from the draft and add new publication date
    new_data = convert_json(new_version_response, new_date, publisher)
    update_url =  API_URL+f"records/{new_id}/draft"
    # update draft dataset with the new publication date
    draft_response = requests.put(update_url, headers=json_header, json=new_data)

    return draft_response.json()["id"]
