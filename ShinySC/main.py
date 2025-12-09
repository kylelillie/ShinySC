import re
import json
import requests
import urllib.parse
from datetime import datetime

_cached_metadata = None
_cached_cube_list = None

_codes = requests.get('https://www150.statcan.gc.ca/t1/wds/rest/getCodeSets')
_codes = _codes.json()

def _cube_list(id='',lang='en'):
    """
    Retrieves information about a cube (table).

    Args:
        id (int or str): The product ID (PID)
        lang (str): The language ('en' or 'fr')
    """

    global _cached_cube_list

    try:
        if _cached_cube_list == None:
            url = "https://www150.statcan.gc.ca/t1/wds/rest/getAllCubesList"
            resp = requests.get(url)
            table = resp.json()
            _cached_cube_list = table

        else:
            table = _cached_cube_list

    except Exception as e:
        print('Failed to find "getAllCubesList" on WDS')

    if id == '':
        return table

    for i in table:
        if i['productId'] == id: return i
    else:
        print(f'Table {id} not found.')

def _remove_lang(obj,language):
    
    language = 'En' if language == 'en' else 'Fr'

    if isinstance(obj, dict):
        
        obj = {k: _remove_lang(v,language) for k, v in obj.items() if not k.endswith(language)}

        for k in obj.keys():
            if isinstance(obj[k],list):
                if len(obj[k]) > 0:
                    if isinstance(obj[k][0],dict):
                        obj[k] = [_remove_lang(i,language) for i in obj[k]]
        return obj
    
    else:
        return obj

def _search_json(obj: dict={}, term: str='', mode: str='AND'):
    """
    Recursively search JSON-like structures.
    Keep entries if:
      - key contains term
      - OR value contains term
      - OR nested match
      - OR sibling key contains "code" when any match occurs in the same dict
    """

    mode = mode.upper()

    if mode == "OR":
        terms = [t.strip() for t in term.split(",") if t.strip()]
        pattern = re.compile("|".join(map(re.escape, terms)), re.IGNORECASE | re.DOTALL)

    if mode == "AND":
        regex = "".join(f"(?=.*{re.escape(t)})" for t in term) + ".*"
        pattern = re.compile(regex, re.IGNORECASE | re.DOTALL)

    # Case 1: dict
    if isinstance(obj, dict):
        matches = {}              # matches found in this dict
        matched_in_dict = False   # flag so we can keep sibling "code" keys

        # First pass: detect matches
        child_results = {}
        for k, v in obj.items():
            #key_match = term in k.lower()
            #value_match = isinstance(v, str) and term in v.lower()
            key_match = bool(pattern.search(k))
            value_match = isinstance(v, str) and bool(pattern.search(v))

            nested = None

            if isinstance(v, (dict, list)):
                #nested = _search_json(v, term)
                nested = _search_json(v, term, mode)

            # If this entry matches directly or via nested
            if key_match or value_match or nested:
                matched_in_dict = True
                child_results[k] = nested if nested is not None else v

        # Second pass: if any match happened, also keep sibling "code" keys
        if matched_in_dict:
            for k, v in obj.items():
                if "Code" in k and k not in child_results:
                    child_results[k] = v

        return child_results if child_results else None

    # Case 2: list
    elif isinstance(obj, list):
        results = []
        for item in obj:
            nested = _search_json(item, term, mode)
            #value_match = isinstance(item, str) and term in item
            value_match = isinstance(item, str) and bool(pattern.search(item))

            if nested is not None or value_match:
                results.append(nested if nested is not None else item)

        return results if results else None

    # Case 3: primitive
    else:
        #if isinstance(obj, str) and term in obj:
        if isinstance(obj, str) and bool(re.search(obj)):
            return obj
        return None

def _parse_dim(x,full=True):

    tmp = {}
    sel = []

    if full:
        for i in x:
            try:
                tmp[i['dimensionNameEn']] = i['member']
                j = []
                for k in i['member']:
                    j.append(k['memberId'])
            except:
                tmp[i['dimensionNameEn']] = i['hasUom']

            sel.append(j)
    else:
        pass
    
    return tmp,sel

def _parse_filters(filters,id,lang='en'):
    """
    Takes user-defined filters as a dictionary and
    transforms it to use in the StatCan URL.

    Args:
        filters (dict): User-defined filters
    """
    #Iterate over dict; put it in same order metadata has them;
    #Then convert selected items into their numeric entries as nested list
    #--> Convert dimensionName to dimensionPositionId; this lets us put in right order
    #-->---> Convert members' memberNameEn(Fr) to memberId
    #There will be some "easy" filters, like '503' to select all CMAs in geography
    #...though I guess that would be applied after the table is downloaded

    tmp = full_metadata(id)
    dim = tmp['dimension']

    new_filters = []

    for i in range(0,len(dim)):

        dim_name = dim[i][f'dimensionName{lang.capitalize()}']

        if dim_name in filters:

            selected_names = filters[dim_name]
            selected_ids = []

            for j in dim[i]['member']:

                if j[f'memberName{lang.capitalize()}'] in selected_names:
                    selected_ids.append(j['memberId'])

            new_filters.append(selected_ids)

        else:
            #Select all members if not specified in filters
            selected_ids = []
            for j in dim[i]['member']:
                selected_ids.append(j['memberId'])
            new_filters.append(selected_ids)
    
    raw = json.dumps(new_filters, separators=(',',':'))
    enc = urllib.parse.quote(raw)

    return enc

def full_metadata(id, timeout=30, lang='en', special=[]):
    """
    Retrieves metadata for a cube (table) from Statistics Canada WDS.

    Args:
        id (int or str): The product ID (PID) of the cube (e.g., 35100003).
        timeout (float): Timeout in seconds for the HTTP request.
        lang (str): Language preference for the metadata ('en', 'fr', or 'all').

    Returns:
        dict: JSON response object converted to Python dict.
    """

    endpoint = "https://www150.statcan.gc.ca/t1/wds/rest/getCubeMetadata"

    # Prepare payload as list of dicts, per documentation example. :contentReference[oaicite:2]{index=2}
    payload = [
        {
            "productId": str(id)
        }
    ]

    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
   
        # Check for status
        if data[0]["status"] != "SUCCESS":
            raise RuntimeError(f"Request returned non-SUCCESS status: {data}")
        
        if lang == 'en':
            return _remove_lang(data[0]['object'],'Fr')
        
        elif lang == 'fr':
            return _remove_lang(data[0]['object'],'En')
        
        else:
            return data[0]['object']
    
    except requests.RequestException as e:
        raise RuntimeError(f"HTTP request failed: {e}") from e
    
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse JSON response: {e}") from e

def simple_metadata(id, lang='en'):
    """
    Retrieves and displays simplified metadata for a cube (table).\n
    This will only show productId, cubeTitle, cubeEndDate, cubeStartDate, and a simplified dimension.

    Args:
        id (int or str): The product ID (PID)
        lang (str): The language ('en' or 'fr')
    """

    meta = full_metadata(id,30,lang)

    keep = ['productId',f'cubeTitle{lang.capitalize}','cubeEndDate','cubeStartDate','dimension']

    obj = {k:v for k,v in meta.items() if k in keep}

    return obj

def instructions():
    print("""
---------------------------------------------------------
If you already know the productId for the table you want,
call ShinySC.describe(productId) to see available dimensions
that can be used for filtering.
            
You can then copy/paste the key:[values...] you want into
a variable that is passed into ShinySC.make_url(filters={...})
          
You can search for tables using ShinySC.search() to find 
data tables by geography, attribute, name, date, subject, etc.
          
This library makes use of these endpoints:
https://www150.statcan.gc.ca/t1/wds/rest/getCodeSets
https://www150.statcan.gc.ca/t1/wds/rest/getAllCubesList
https://www150.statcan.gc.ca/t1/wds/rest/getCubeMetadata
---------------------------------------------------------
""")

def describe(id, lang='en'):
    """
    Quickly get key information to help you build a custom query.

    Args:
        id (str, int): productId
        lang (str): The language ('en' or 'fr')
    """

    attributes = {}

    md = full_metadata(id,30,lang)

    attributes['name'] = md[f'cubeTitle{lang.capitalize()}']
    attributes['dataPoints'] = md['nbDatapointsCube']
    attributes['productId'] = id
    attributes['status'] = 'Active' if md['archiveStatusCode'] == '2' else 'Archived'
    attributes['dataDateRange'] = [md['cubeStartDate'],md['cubeEndDate']]
    attributes['lastUpdated'] = md['releaseTime']
    attributes['subject'] = md['subjectCode']
    attributes['dimensions'] = [
        {i[f'dimensionName{lang.capitalize()}']:[j[f'memberName{lang.capitalize()}'] for j in i['member']]} for i in md['dimension']
        ]

    return attributes

def make_url(id: int='',periods: int='',start: str='',end: str='',full: bool=False,filters: dict={},region_type: str='',lang: str='en'):
    """
    Downloads a table from Statistics Canada using custom filters.
    Default language is English ('en')
    Returns a URL that can be downloaded with your favourite library.

    Args:
        :param id (int, str): productId
        :param periods (int): number of recent periods you wish to download (default is 1)
        :param start (str): desired start date for data series (YYYY-MM-DD)
        :param end (str): desired end date for data series (YYYY-MM-DD)
        :param full (bool): download the full table or not (default True)
        :param filters (dict): filters you wish to apply ('attribute':[...],...)
        :param lang (str): which langauge you wish to get data in ('en'[default] or 'fr')
    """
    global _cached_metadata

    try:
        if _cached_metadata == None:
            md= full_metadata(id,30,lang)
        else:
            md = _cached_metadata
    except:
        print('Invalid productId.')
        return ''

    #tablename = md['cubeTitleEn']
    archived = md['archiveStatusCode']
    lastUpdated = md['releaseTime']
    checked_levels = ''

    if archived == '1': print(f'ADVISORY: This table has been archived and does not get updated. Last updated: {lastUpdated}')

    if filters == {} and not full:
        print('ADVISORY: No filters specified. Generating URL for the full table. Full tables can be very large.')
        full = True

    if full:
        dim = md['dimension']
        dim,selected = _parse_dim(dim,full)
        raw = json.dumps(selected, separators=(',',':'))
        #checked_levels = '%2C1%2C2%2C3'
        #filters = ''
        filters = urllib.parse.quote(raw)

    else:
        filters = _parse_filters(filters,id,lang)

    url = f'https://www150.statcan.gc.ca/t1/tbl1/en/dtl!downloadDbLoadingData-nonTraduit.action?pid={id}01&latestN={periods}&startDate={start}&endDate={end}&csvLocale={lang}&selectedMembers={filters}&checkedLevels='

    if region_type != '':
        df = df[df.DGUID.str[6:9] == region_type]

    return url

def search(query='',last_updated='',dates=[],status='2',mode='AND',lang='en'):
    """
    Docstring for find_tables
    
    :param query (str): Table attributes you want to search for (names, geographies, etc.)
    :param status (str): Active or Archived
    :param last_updated (str): Description
    :param dates ([str,str]): Description
    :param mode (str): 'AND'[default] or 'OR' search mode for query terms
    :param lang (str): Language ('en' or 'fr')
    """

    global _codes

    #Need to look over the code descriptions and grab relevant codes.
    #Can use this list to filter down datasets that are then searched in name and description

    local_codes = _remove_lang(_codes,'Fr' if lang == 'en' else 'En')
    local_codes = _search_json(local_codes,query,mode)

    parsed_local_codes = {}

    for k in local_codes['object'].keys():
        parsed_local_codes[k] = []
        for i in local_codes['object'][k]:
            try:
                parsed_local_codes[k].append(i[f'{k}Code'])
            except:
                pass
    
    tables = _cube_list()
    filtered_tables = []

    for t in tables:

        if query.lower() in t[f'cubeTitle{lang.capitalize()}'].lower():
            if (t['productId'] not in filtered_tables) & (t['archived'] == status):
                filtered_tables.append(t['productId'])

        for k in parsed_local_codes.keys():

            if  (t['productId'] not in filtered_tables) & (t['archived'] == status):
                if (k == 'subject') & (len(parsed_local_codes[k]) > 0) & ('subjectCode' in t):
                    try:
                        filtered_tables.append(t['productId']) if set(parsed_local_codes[k]).intersection(set(t['subjectCode'])) else None
                    except:
                        pass

                if (k == 'survey') & (len(parsed_local_codes[k]) > 0) & (t['surveyCode'] != None):
                    try:
                        filtered_tables.append(t['productId']) if set(parsed_local_codes[k]).intersection(set(t['surveyCode'])) else None
                    except:
                        pass

    print(f'Found {len(filtered_tables)} tables matching search criteria, "{query}".\n')

    return filtered_tables

def list_tables(lang='en'):


    url = "https://www150.statcan.gc.ca/t1/wds/rest/getAllCubesList"
    resp = requests.get(url)
    tables = resp.json()

    df = pd.DataFrame(tables)

    if lang == 'en':
        df = df[[x for x in df.columns if x if 'Fr' not in x]]
    elif lang == 'fr':
        df = df[[x for x in df.columns if x if 'En' not in x]]

    df = df[df['archived'] == '2']

    archived_tables = df[df['archived'] == '1']
    active_tables = df[df['archived'] == '2']

    card_css = "border:1px solid black;margin:10px;padding:10px;background:white;max-width:200px;border-radius:3px;color:black;"
    n = 2

    count = 0

    for p in tables:

        id = p['productId']
        endDate = datetime.fromisoformat(p['cubeEndDate'].replace("Z", "+00:00")).replace(tzinfo=None)

        if p['archived'] == '2':

            metadata = full_metadata(id)
            num_dimensions = len(metadata['dimension'])
            data = metadata['dimension']

            tablename = p['cubeTitleEn']
            dim = p['dimensions']
            dim,selected = _parse_dim(dim)

            raw = json.dumps(selected, separators=(',',':'))
            enc = urllib.parse.quote(raw)

            num_param = len(data)

            attributes = {}
            attributes['Table Name'] = tablename

            for i in range(0,num_param):

                sub_size = len(data[i]['member'])
                top_name = data[i]['dimensionNameEn']

                for j in range(0,sub_size):
                    
                    #print(data[i]['member'][j])

                    name = data[i]['member'][j]['memberNameEn']
                    classification = data[i]['member'][j]['classificationCode']

                    if top_name in attributes:
                        attributes[top_name].append(name)
                    else:
                        attributes[top_name] = [name]

            print(id,' - ',tablename,'\n',attributes)
            #get_table(id=id,n=n,enc=enc)#region_type='503')
            
            count += 1

