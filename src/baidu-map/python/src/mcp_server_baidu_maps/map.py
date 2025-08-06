# map.py
import os
import copy
import httpx
from asyncio import sleep
 
from mcp.server.fastmcp import FastMCP
import mcp.types as types
import re
 
# 创建MCP服务器实例
mcp = FastMCP(
    name="mcp-server-baidu-maps",
    instructions="This is a MCP server for Baidu Maps."
)

"""

获取环境变量中的API密钥, 用于调用百度地图API
环境变量名为: BAIDU_MAPS_API_KEY, 在客户端侧通过配置文件进行设置传入
获取方式请参考: https://lbsyun.baidu.com/apiconsole/key; 

"""

api_key = os.getenv('BAIDU_MAPS_API_KEY')
api_url = "https://api.map.baidu.com"
 
 
def filter_result(data) -> dict:
    """
    过滤路径规划结果, 用于剔除冗余字段信息, 保证输出给模型的数据更简洁, 避免长距离路径规划场景下chat中断
    """
    
    # 创建输入数据的深拷贝以避免修改原始数据
    processed_data = copy.deepcopy(data)
    
    # 检查是否存在'result'键
    if 'result' in processed_data:
        result = processed_data['result']
        
        # 检查'result'中是否存在'routes'键
        if 'routes' in result:
            for route in result['routes']:
                # 检查每个'route'中是否存在'steps'键
                if 'steps' in route:
                    new_steps = []
                    for step in route['steps']:
                        # 提取'instruction'字段, 若不存在则设为空字符串
                        new_step = {
                            'distance': step.get('distance', ''),
                            'duration': step.get('duration', ''),
                            'instruction': step.get('instruction', '')
                        }
                        new_steps.append(new_step)
                    # 替换原steps为仅含instruction的新列表
                    route['steps'] = new_steps
    
    return processed_data


def is_latlng(text):
    """
    判断输入是否为经纬度坐标.
    """
    
    # 允许有空格，支持正负号和小数
    pattern = r'^\s*([+-]?\d+(?:\.\d+)?)\s*,\s*([+-]?\d+(?:\.\d+)?)\s*$'
    match = re.match(pattern, text)
    if not match:
        return False
    lat, lng = float(match.group(1)), float(match.group(2))
    # 简单经纬度范围校验
    return -90 <= lat <= 90 and -180 <= lng <= 180

def mask_api_key(text: str) -> str:
    """
    信息脱敏函数，主要用于给某个字符串脱敏用户的ak
    可以处理包含API key的复杂字符串，如URL、错误信息等
    """
    if not text or not api_key:
        return text
    
    # 如果字符串中不包含api_key，直接返回
    if api_key not in text:
        return text
    
    # 计算脱敏后的API key
    if len(api_key) <= 8:
        # 如果api_key长度较短，只显示前2位和后2位
        masked_key = api_key[:2] + '*' * (len(api_key) - 4) + api_key[-2:]
    else:
        # 如果api_key长度较长，显示前4位和后4位
        masked_key = api_key[:4] + '*' * (len(api_key) - 8) + api_key[-4:]
    
    # 替换文本中所有出现的api_key
    return text.replace(api_key, masked_key)


async def map_geocode(
    name: str, arguments: dict
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    地理编码服务, 将地址解析为对应的位置坐标.
    """
    try:
        address = arguments.get("address", "")
        is_china = arguments.get("is_china", "true")
        url = ""
        
        # 调用百度API
        if is_china == "true":
            url = f"{api_url}/geocoding/v3/"
        else:
            url = f"{api_url}/api_geocoding_abroad/v1/"
                
        # 设置请求参数
        params = {
            "ak": f"{api_key}",
            "output": "json",
            "address": f"{address}",
            "from": "py_mcp"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            result = response.json()
 
        if result.get("status") != 0:
            error_msg = result.get("message", "unknown error")
            raise Exception(f"API response error: {mask_api_key(error_msg)}")
 
        return [types.TextContent(type="text", text=response.text)]
 
    except httpx.HTTPError as e:
        raise Exception(f"HTTP request failed: {str(e)}") from e
    except KeyError as e:
        raise Exception(f"Failed to parse reponse: {str(e)}") from e


async def map_reverse_geocode(
    name: str, arguments: dict
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    逆地理编码服务, 根据纬经度坐标获取对应位置的地址描述.
    """
    try:
        latitude = arguments.get("latitude", "")
        longitude = arguments.get("longitude", "")

        # 调用百度API
        url = f"{api_url}/reverse_geocoding/v3/"
        
        params = {
            "ak": f"{api_key}",
            "output": "json",
            "location": f"{latitude},{longitude}",
            "extensions_road": "true",
            "extensions_poi": "1",
            "entire_poi": "1",
            "from": "py_mcp"
        }
 
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            result = response.json()
 
        if result.get("status") != 0:
            error_msg = result.get("message", "unknown error")
            raise Exception(f"API response error: {mask_api_key(error_msg)}")
 
        return [types.TextContent(type="text", text=response.text)]
 
    except httpx.HTTPError as e:
        raise Exception(f"HTTP request failed: {str(e)}") from e
    except KeyError as e:
        raise Exception(f"Failed to parse reponse: {str(e)}") from e


async def map_search_places(
    name: str, arguments: dict
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    地点检索服务, 支持检索城市内的地点信息或圆形区域内的周边地点信息.
    """
    try:
        query = arguments.get("query", "")
        tag = arguments.get("tag", "")
        region = arguments.get("region", "全国") # 默认检索全国，防止出错
        location = arguments.get("location", "")
        radius = arguments.get("radius", "")
        language = arguments.get("language", "")
        is_china = arguments.get("is_china", "true")
        
        url = ""
        params = {
            "ak": f"{api_key}",
            "output": "json",
            "query": f"{query}",
            "type": f"{tag}",
            # "photo_show": "true",
            "region_limit": "true",
            "scope": 2,
            "from": "py_mcp",
            "language": f"{language}"
        }
        
        if is_china == "true":
            if location:
                url = f"{api_url}/place/v3/around"
                params["location"] = f"{location}"
                params["radius"] = f"{radius}"
            else:
                url = f"{api_url}/place/v3/region"
                params["region"] = f"{region}"
        elif is_china == "false":
            url = f"{api_url}/place_abroad/v1/search"
            if location:
                params["location"] = f"{location}"
                params["radius"] = f"{radius}"
            else:
                params["region"] = f"{region}"
        else:
            raise Exception("input `is_china` invaild, please reinput `is_china` with `true` or `false`")

 
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            result = response.json()
 
        if result.get("status") != 0:
            error_msg = result.get("message", "unknown error")
            
            raise Exception(f"API response error: {mask_api_key(error_msg)}")
 
        return [types.TextContent(type="text", text=response.text)]
 
    except httpx.HTTPError as e:
        raise Exception(f"HTTP request failed: {str(e)}") from e
    except KeyError as e:
        raise Exception(f"Failed to parse reponse: {str(e)}") from e


async def map_place_details(
    name: str, arguments: dict
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    地点详情检索服务, 获取指定POI的详情信息.
    """
    try:
        uid = arguments.get("uid", "")
        is_china = arguments.get("is_china", "true")
        url = ""
        
        if is_china == "true":
            url = f"{api_url}/place/v2/detail"
        else:
            url = f"{api_url}/place_abroad/v1/detail"
        
        params = {
            "ak": f"{api_key}",
            "output": "json",
            "uid": f"{uid}",
            "scope": 2,
            "from": "py_mcp"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            result = response.json()
 
        if result.get("status") != 0:
            error_msg = result.get("message", "unknown error")
            raise Exception(f"API response error: {mask_api_key(error_msg)}")
 
        return [types.TextContent(type="text", text=response.text)]
 
    except httpx.HTTPError as e:
        raise Exception(f"HTTP request failed: {str(e)}") from e
    except KeyError as e:
        raise Exception(f"Failed to parse reponse: {str(e)}") from e


async def map_directions_matrix(
    name: str, arguments: dict
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    批量算路服务, 根据起点和终点坐标计算路线规划距离和行驶时间.
    """
    try:
        origins = arguments.get("origins", "")
        destinations = arguments.get("destinations", "")
        model = arguments.get("model", "driving")
        
        url = f"{api_url}/routematrix/v2/{model}"
        
        params = {
            "ak": f"{api_key}",
            "output": "json",
            "origins": f"{origins}",
            "destinations": f"{destinations}",
            "from": "py_mcp"
        }
 
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            result = response.json()
 
        if result.get("status") != 0:
            error_msg = result.get("message", "unknown error")
            raise Exception(f"API response error: {mask_api_key(error_msg)}")
 
        return [types.TextContent(type="text", text=response.text)]
 
    except httpx.HTTPError as e:
        raise Exception(f"HTTP request failed: {str(e)}") from e
    except KeyError as e:
        raise Exception(f"Failed to parse reponse: {str(e)}") from e


async def map_directions(
    name: str, arguments: dict
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    路线规划服务, 支持驾车、骑行、步行和公交路线规划.
    """
    try:
        model = arguments.get("model", "driving")
        origin = arguments.get("origin", "")
        destination = arguments.get("destination", "")
        is_china = arguments.get("is_china", "true")
        url = ""
        
        # 检查输入是否为地址文本（不包含逗号）
        if not is_latlng(origin):
            # 调用地理编码服务获取起点经纬度
            geocode_url = ""
            if is_china == "true":
                geocode_url = f"{api_url}/geocoding/v3/"
            else:
                geocode_url = f"{api_url}/api_geocoding_abroad/v1/"
            geocode_params = {
                "ak": f"{api_key}",
                "output": "json",
                "address": origin,
                "from": "py_mcp"
            }
            
            async with httpx.AsyncClient() as client:
                geocode_response = await client.get(geocode_url, params=geocode_params)
                geocode_response.raise_for_status()
                geocode_result = geocode_response.json()
                
                if geocode_result.get("status") != 0:
                    error_msg = geocode_result.get("message", "input `origin` invaild, please reinput more detail address")
                    raise Exception(f"Geocoding API error: {mask_api_key(error_msg)}")
                
                location = geocode_result.get("result", {}).get("location", {})
                origin = f"{location.get('lat')},{location.get('lng')}"
        
        if not is_latlng(destination):
            # 调用地理编码服务获取终点经纬度
            geocode_url = ""
            if is_china == "true":
                geocode_url = f"{api_url}/geocoding/v3/"
            else:
                geocode_url = f"{api_url}/api_geocoding_abroad/v1/"
            geocode_params = {
                "ak": f"{api_key}",
                "output": "json",
                "address": destination,
                "from": "py_mcp"
            }
            
            async with httpx.AsyncClient() as client:
                geocode_response = await client.get(geocode_url, params=geocode_params)
                geocode_response.raise_for_status()
                geocode_result = geocode_response.json()
                
                if geocode_result.get("status") != 0:
                    error_msg = geocode_result.get("message", "input `destination` invaild, please reinput more detail address")
                    raise Exception(f"Geocoding API error: {mask_api_key(error_msg)}")
                
                location = geocode_result.get("result", {}).get("location", {})
                destination = f"{location.get('lat')},{location.get('lng')}"
        
        # 调用路线规划服务
        url = ""
        if is_china == "true":
            url = f"{api_url}/directionlite/v1/{model}"
        else:
            url = f"{api_url}/direction_abroad/v1/{model}"
        
        params = {
            "ak": f"{api_key}",
            "output": "json",
            "origin": origin,
            "destination": destination,
            "from": "py_mcp"
        }
 
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            result = response.json()
 
        if result.get("status") != 0:
            error_msg = result.get("message", "unknown error")
            raise Exception(f"API response error: {mask_api_key(error_msg)}")
 
        # if model == 'transit':
        #     return [types.TextContent(type="text", text=response.text)]
        # else:
        #     return [types.TextContent(type="text", text=str(filter_result(result)))]
        return [types.TextContent(type="text", text=response.text)]
 
    except httpx.HTTPError as e:
        raise Exception(f"HTTP request failed: {str(e)}") from e
    except KeyError as e:
        raise Exception(f"Failed to parse response: {str(e)}") from e


async def map_weather(
    name: str, arguments: dict
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    天气查询服务, 查询实时天气信息及未来5天天气预报.
    """
    try:
        location = arguments.get("location", "")
        district_id = arguments.get("district_id", "")
        is_china = arguments.get("is_china", "true")
        url = ""
        
        if is_china == "true":
            url = f"{api_url}/weather/v1/?"
        else:
            url = f"{api_url}/weather_abroad/v1/?"
        
        params = {
            "ak": f"{api_key}",
            "data_type": "all",
            "from": "py_mcp"
        }
        
        if not location:
            params["district_id"] = f"{district_id}"
        else:
            params["location"] = f"{location}"
 
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            result = response.json()
 
        if result.get("status") != 0:
            error_msg = result.get("message", "unknown error")
            raise Exception(f"API response error: {mask_api_key(error_msg)}")
 
        return [types.TextContent(type="text", text=response.text)]
 
    except httpx.HTTPError as e:
        raise Exception(f"HTTP request failed: {str(e)}") from e
    except KeyError as e:
        raise Exception(f"Failed to parse reponse: {str(e)}") from e


async def map_ip_location(
    name: str, arguments: dict
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    IP定位服务, 通过所给IP获取具体位置信息和城市名称, 可用于定位IP或用户当前位置.
    """
    try:
        ip = arguments.get("ip", "")
        
        url = f"{api_url}/location/ip"
        
        params = {
            "ak": f"{api_key}",
            "from": "py_mcp",
            "ip": ip
        }
 
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            result = response.json()
 
        if result.get("status") != 0:
            error_msg = result.get("message", "unknown error")
            raise Exception(f"API response error: {mask_api_key(error_msg)}")
 
        return [types.TextContent(type="text", text=response.text)]
 
    except httpx.HTTPError as e:
        raise Exception(f"HTTP request failed: {str(e)}") from e
    except KeyError as e:
        raise Exception(f"Failed to parse reponse: {str(e)}") from e


async def map_road_traffic(
    name: str, arguments: dict
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    实时路况查询服务, 查询实时交通拥堵情况.
    """
    try:
        model = arguments.get("model", "")
        road_name = arguments.get("road_name", "")
        city = arguments.get("city", "")
        bounds = arguments.get("bounds", "")
        vertexes = arguments.get("vertexes", "")
        center = arguments.get("center", "")
        radius = arguments.get("radius", "")
        
        url = f"{api_url}/traffic/v1/{model}?"
        
        params = {
            "ak": f"{api_key}",
            "output": "json",
            "from": "py_mcp"
        }
        
        if model == 'bound':
            params['bounds'] = f'{bounds}'
        elif model == 'polygon':
            params['vertexes'] = f'{vertexes}'
        elif model == 'around':
            params['center'] = f'{center}'
            params['radius'] = f'{radius}'
        elif model == 'road':
            params['road_name'] = f'{road_name}'
            params['city'] = f'{city}'
 
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            result = response.json()
 
        if result.get("status") != 0:
            error_msg = result.get("message", "unknown error")
            raise Exception(f"API response error: {mask_api_key(error_msg)}")
 
        return [types.TextContent(type="text", text=response.text)]
 
    except httpx.HTTPError as e:
        raise Exception(f"HTTP request failed: {str(e)}") from e
    except KeyError as e:
        raise Exception(f"Failed to parse reponse: {str(e)}") from e


async def map_poi_extract(
    name: str,
    arguments: dict
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    POI智能提取
    """
    # 关于高级权限使用的相关问题，请联系我们: https://lbsyun.baidu.com/apiconsole/fankui?typeOne=%E4%BA%A7%E5%93%81%E9%9C%80%E6%B1%82&typeTwo=%E9%AB%98%E7%BA%A7%E6%9C%8D%E5%8A%A1
    
    try:
        text_content = arguments.get("text_content", "")
 
        # 调用POI智能提取的提交接口
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        submit_url = f"{api_url}/api_mark/v1/submit"
        result_url = f"{api_url}/api_mark/v1/result"
        
        # 设置上传用户描述的请求体
        submit_body = {
            "ak": f"{api_key}",
            "id": 0,
            "msg_type": "text",
            "text_content": f"{text_content}",
            "from": "py_mcp"
        }

        # 异步请求
        async with httpx.AsyncClient() as client:
            # 提交任务
            submit_resp = await client.post(
                submit_url, data=submit_body, headers=headers, timeout=10.0
            )
            submit_resp.raise_for_status()
            submit_result = submit_resp.json()

            if submit_result.get("status") != 0:
                error_msg = submit_result.get("message", "unknown error")
                raise Exception(f"API response error: {mask_api_key(error_msg)}")
            

            map_id = submit_result.get("result", {}).get("map_id")
            if not map_id:
                raise Exception("Can not found map_id")

            # 轮询获取结果（最多5次，间隔2秒）
            result_body = {"ak": api_key, "id": 0, "map_id": map_id, "from": "py_mcp"}
            max_retries = 5
            for attempt in range(max_retries):
                result_resp = await client.post(
                    result_url, data=result_body, headers=headers, timeout=10.0
                )
                result_resp.raise_for_status()
                result = result_resp.json()

                if result.get("status") == 0 and result.get("result"):
                    return result
                elif attempt < max_retries - 1:
                    await sleep(2)
            
            else:
                raise Exception("Timeout to get the result")
                
        if result.get("status") != 0:
            error_msg = result.get("message", "unknown error")
            raise Exception(f"API response error: {error_msg}")

    except httpx.HTTPError as e:
        raise Exception(f"HTTP request failed: {str(e)}") from e
    except KeyError as e:
        raise Exception(f"Failed to parse reponse: {str(e)}") from e
    

async def list_tools() -> list[types.Tool]:
    """
    列出所有可用的工具。
    
    Args:
        None.
    
    Returns:
        list (types.Tool): 包含了所有可用的工具, 每个工具都包含了名称、描述、输入schema三个属性.
    """
    return [
        types.Tool(
            name="map_geocode",
            description="地理编码服务: 将地址解析为对应的位置坐标.地址结构越完整, 地址内容越准确, 解析的坐标精度越高.",
            inputSchema={
                "type": "object",
                "required": ["address"],
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "待解析的地址.最多支持84个字节.可以输入两种样式的值, 分别是：\n1、标准的结构化地址信息, 如北京市海淀区上地十街十号\n2、支持*路与*路交叉口描述方式, 如北一环路和阜阳路的交叉路口\n第二种方式并不总是有返回结果, 只有当地址库中存在该地址描述时才有返回",
                    },
                    "is_china": {
                        "type": "string",
                        "description": "查询地是否在中国大陆以外地区, 可选值为`true`或`false`, 默认为`true`",
                    },
                },
            }
        ),
        types.Tool(
            name="map_reverse_geocode",
            description="逆地理编码服务: 根据纬经度坐标, 获取对应位置的地址描述, 所在行政区划, 道路以及相关POI等信息",
            inputSchema={
                "type": "object",
                "required": ["latitude", "longitude"],
                "properties": {
                    "latitude": {
                        "type": "number",
                        "description": "纬度 (bd09ll)",
                    },
                    "longitude": {
                        "type": "number",
                        "description": "经度 (bd09ll)",
                    },
                },
            }
        ),
        types.Tool(
            name="map_search_places",
            description="地点检索服务: 支持检索全球各城市内的地点信息(最小到city级别), 也可支持圆形区域内的周边地点信息检索."
                        "\n城市内检索: 检索某一城市内（目前最细到城市级别）的地点信息."
                        "\n周边检索: 设置圆心和半径, 检索圆形区域内的地点信息（常用于周边检索场景）.",
            inputSchema={
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "检索关键字, 可直接使用名称或类型, 如'天安门', 且可以至多10个关键字, 用英文逗号隔开",
                    },
                    "tag": {
                        "type": "string",
                        "description": "检索分类, 以中文字符输入, 如'美食', 多个分类用英文逗号隔开, 如'美食,购物'",
                    },
                    "region": {
                        "type": "string",
                        "description": "检索的城市名称, 可为行政区划名或citycode, 格式如'北京市'或'131', 不传默认为'全国', 当is_china为false时, 该参数必传且只能传文本, 如'东京'",
                    },
                    "location": {
                        "type": "string",
                        "description": "圆形区域检索的中心点纬经度坐标, 格式为lat,lng",
                    },
                    "radius": {
                        "type": "integer",
                        "description": "圆形区域检索半径, 单位：米",
                    },
                    "is_china": {
                        "type": "string",
                        "description": "检索地是否在中国大陆以外地区, 可选值为`true`或`false`, 默认为`true`",
                    },
                },
            }
        ),
        types.Tool(
            name="map_place_details",
            description="地点详情检索服务: 地点详情检索针对指定POI, 检索其相关的详情信息."
                        "\n通过地点检索服务获取POI uid.使用地点详情检索功能, 传入uid, 即可检索POI详情信息, 如评分、营业时间等(不同类型POI对应不同类别详情数据).",
            inputSchema={
                "type": "object",
                "required": ["uid"],
                "properties": {
                    "uid": {
                        "type": "string",
                        "description": "POI的唯一标识",
                    },
                    "is_china": {
                        "type": "string",
                        "description": "查询地是否在中国大陆以外地区, 可选值为`true`或`false`, 默认为`true`",
                    },
                },
            }
        ),
        types.Tool(
            name="map_directions_matrix",
            description="批量算路服务: 根据起点和终点坐标计算路线规划距离和行驶时间."
                        "\n批量算路目前支持驾车、骑行、步行."
                        "\n步行时任意起终点之间的距离不得超过200KM, 超过此限制会返回参数错误."
                        "\n驾车批量算路一次最多计算100条路线, 起终点个数之积不能超过100.",
            inputSchema={
                "type": "object",
                "required": ["origins", "destinations"],
                "properties": {
                    "origins": {
                        "type": "string",
                        "description": "多个起点纬经度坐标, 纬度在前, 经度在后, 多个起点用|分隔",
                    },
                    "destinations": {
                        "type": "string",
                        "description": "多个终点纬经度坐标, 纬度在前, 经度在后, 多个终点用|分隔",
                    },
                    "model": {
                        "type": "string",
                        "description": "批量算路类型(driving, riding, walking)",
                    },
                },
            }
        ),
        types.Tool(
            name="map_directions",
            description="路线规划服务: 根据起终点`位置名称`或`纬经度坐标`规划出行路线."
                        "\n驾车路线规划: 根据起终点`位置名称`或`纬经度坐标`规划驾车出行路线."
                        "\n骑行路线规划: 根据起终点`位置名称`或`纬经度坐标`规划骑行出行路线."
                        "\n步行路线规划: 根据起终点`位置名称`或`纬经度坐标`规划步行出行路线."
                        "\n公交路线规划: 根据起终点`位置名称`或`纬经度坐标`规划公共交通出行路线.",
            inputSchema={
                "type": "object",
                "required": ["origin", "destination"],
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "路线规划类型(driving, riding, walking, transit)",
                    },
                    "origin": {
                        "type": "string",
                        "description": "起点位置名称或纬经度坐标, 纬度在前, 经度在后",
                    },
                    "destination": {
                        "type": "string",
                        "description": "终点位置名称或纬经度坐标, 纬度在前, 经度在后",
                    },
                    "is_china": {
                        "type": "string",
                        "description": "查询地是否在中国大陆以外地区, 可选值为`true`或`false`, 默认为`true`",
                    },
                },
            }
        ),
        types.Tool(
            name="map_weather",
            description="天气查询服务: 通过行政区划或是经纬度坐标查询实时天气信息及未来5天天气预报.",
            inputSchema={
                "type": "object",
                "required": [],
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "经纬度坐标, 经度在前纬度在后, 逗号分隔",
                    },
                    "district_id": {
                        "type": "string",
                        "description": "行政区划代码, 需保证为6位无符号整数",
                    },
                    "is_china": {
                        "type": "string",
                        "description": "查询地是否在中国大陆以外地区, 可选值为`true`或`false`, 默认为`true`",
                    },
                },
            }
        ),
        types.Tool(
            name="map_ip_location",
            description="IP定位服务: 通过所给IP获取具体位置信息和城市名称, 可用于定位IP或用户当前位置.",
            inputSchema={
                "type": "object",
                "required": [],
                "properties": {
                    "ip": {
                        "type": "string",
                        "description": "需要定位的IP地址, 如果为空则获取用户当前IP地址(支持IPv4和IPv6)",
                    },
                },
            }
        ),
        types.Tool(
            name="map_road_traffic",
            description="实时路况查询服务: 查询实时交通拥堵情况, 可通过指定道路名和区域形状(矩形, 多边形, 圆形)进行实时路况查询."
                        "\n道路实时路况查询: 查询具体道路的实时拥堵评价和拥堵路段、拥堵距离、拥堵趋势等信息."
                        "\n矩形区域实时路况查询: 查询指定矩形地理范围的实时拥堵情况和各拥堵路段信息."
                        "\n多边形区域实时路况查询: 查询指定多边形地理范围的实时拥堵情况和各拥堵路段信息."
                        "\n圆形区域(周边)实时路况查询: 查询某中心点周边半径范围内的实时拥堵情况和各拥堵路段信息.",
            inputSchema={
                "type": "object",
                "required": ["model"],
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "路况查询类型(road, bound, polygon, around)",
                    },
                    "road_name": {
                        "type": "string",
                        "description": "道路名称和道路方向, model=road时必传 (如:朝阳路南向北)",
                    },
                    "city": {
                        "type": "string",
                        "description": "城市名称或城市adcode, model=road时必传 (如:北京市)",
                    },
                    "bounds": {
                        "type": "string",
                        "description": "区域左下角和右上角的纬经度坐标, 纬度在前, 经度在后, model=bound时必传",
                    },
                    "vertexes": {
                        "type": "string",
                        "description": "多边形区域的顶点纬经度坐标, 纬度在前, 经度在后, model=polygon时必传",
                    },
                    "center": {
                        "type": "string",
                        "description": "圆形区域的中心点纬经度坐标, 纬度在前, 经度在后, model=around时必传",
                    },
                    "radius": {
                        "type": "integer",
                        "description": "圆形区域的半径(米), 取值[1,1000], model=around时必传",
                    },
                },
            }
        ),
        types.Tool(
            name="map_poi_extract",
            description="POI智能提取",
            inputSchema={
                "type": "object",
                "required": ["text_content"],
                "properties": {
                    "text_content": {
                        "type": "string",
                        "description": "根据用户提供的文本描述信息, 智能提取出文本中所提及的POI相关信息. (注意: 使用该服务, api_key需要拥有对应的高级权限, 否则会报错)",
                    },
                },
            }
        )
    ]


async def dispatch(
    name: str, arguments: dict
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    根据名称调度对应的工具函数, 并返回处理结果.
    
    Args:
        name (str): 工具函数的名称, 可选值为: "map_geocode", "map_reverse_geocode",
            "map_search_places", "map_place_details", "map_distance_matrix",
            "map_directions", "map_weather", "map_ip_location", "map_road_traffic",
            "map_mark".
        arguments (dict): 传递给工具函数的参数字典, 包括必要和可选参数.
    
    Returns:
        list[types.TextContent | types.ImageContent | types.EmbeddedResource]: 返回一个列表, 包含文本内容、图片内容或嵌入资源类型的元素.
    
    Raises:
        ValueError: 如果提供了未知的工具名称.
    """
    
    match name:
        case "map_geocode":
            return await map_geocode(name, arguments)
        case "map_reverse_geocode":
            return await map_reverse_geocode(name, arguments)
        case "map_search_places":
            return await map_search_places(name, arguments)
        case "map_place_details":
            return await map_place_details(name, arguments)
        case "map_directions_matrix":
            return await map_directions_matrix(name, arguments)
        case "map_directions":
            return await map_directions(name, arguments)
        case "map_weather":
            return await map_weather(name, arguments)
        case "map_ip_location":
            return await map_ip_location(name, arguments)
        case "map_road_traffic":
            return await map_road_traffic(name, arguments)
        case "map_poi_extract":
            return await map_poi_extract(name, arguments)
        case _:
            raise ValueError(f"Unknown tool: {name}")


# 注册list_tools方法
mcp._mcp_server.list_tools()(list_tools)
# 注册dispatch方法
mcp._mcp_server.call_tool()(dispatch)
 
if __name__ == "__main__":
    mcp.run()
