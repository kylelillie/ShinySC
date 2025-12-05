import requests
import pandas as pd
import urllib.parse
import json
from datetime import datetime
from pprint import pprint


def _table_info(id='',lang='en'):
    """
    Retrieves information about a cube (table).

    Args:
        id (int or str): The product ID (PID)
        lang (str): The language ('en' or 'fr')
    """

    try:
        url = "https://www150.statcan.gc.ca/t1/wds/rest/getAllCubesList"
        resp = requests.get(url)
        table = resp.json()
    except Exception as e:
        print('Failed to find "getAllCubesList" on WDS')

    for i in table:
        if i['productId'] == id: return i
    else:
        print(f'Table {id} not found.')
    
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

    tmp = ssc.full_metadata(id)
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

def full_metadata(id, timeout=30, lang='en'):
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

    def _remove_lang(obj,language):
        
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
call scc.describe(productId) to see available dimensions
that can be used for filtering.
            
You can then copy/paste the key:[values...] you want into
a variable that is passed into scc.get_table(filters={...})
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
    #print(md)
    attributes['name'] = md[f'cubeTitle{lang.capitalize()}']
    attributes['productId'] = id
    attributes['status'] = 'Active' if md['archiveStatusCode'] == '2' else 'Archived'
    attributes['dataDateRange'] = [md['cubeStartDate'],md['cubeEndDate']]
    attributes['lastUpdated'] = md['releaseTime']
    attributes['subject'] = md['subjectCode']
    attributes['dimensions'] = [
        {i[f'dimensionName{lang.capitalize()}']:[j[f'memberName{lang.capitalize()}'] for j in i['member']]} for i in md['dimension']
        ]

    return attributes

def get_table(id='',periods='',start='',end='',full=False,filters={},region_type='',lang='en'):
    """
    Downloads a table from Statistics Canada using custom filters.
    Default language is English ('en')

    Args:
        id (int, str): productId
        periods (int): number of periods you wish to download
        full (bool): download the full table or not (default True)
        filters (dict): filters you wish to apply
        lang (str): which langauge you wish to get data in ('en'[default] or 'fr')
    """
    md = full_metadata(id,30,lang)
    tablename = md['cubeTitleEn']
    archived = md['archiveStatusCode']
    lastUpdated = md['releaseTime']

    if archived == '1': print(f'ADVISORY: This table has been archived and does not get updated. Last updated: {lastUpdated}')

    if filters == {} and not full:
        print('No filters specified. Downloading full table instead.')
        full = True

    if full:
        dim = md['dimension']
        dim,selected = _parse_dim(dim,full)
        raw = json.dumps(selected, separators=(',',':'))
        filters = urllib.parse.quote(raw)

    else:
        filters = _parse_filters(filters,id,lang)

    url = f'https://www150.statcan.gc.ca/t1/tbl1/en/dtl!downloadDbLoadingData-nonTraduit.action?pid={id}01&latestN={periods}&startDate={start}&endDate={end}&csvLocale={lang}&selectedMembers={filters}&checkedLevels='
    
    if full: print('ADVSIORY: Unfiltered tables can be very large')
    print(f'Custom URL: {url}')
    
    try:
        df = pd.read_csv(url)
        display(df)

        if region_type != '':
            df = df[df.DGUID.str[6:9] == region_type]
        
        if df.columns == ['Failed to open stream for the full cube download']:
            print('Failed to open stream. Downloaded file was empty.')

    except Exception as e:
        print(f'Table download failed: {e}')

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