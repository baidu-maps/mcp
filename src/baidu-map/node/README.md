# Baidu Map MCP Server

MCP Server for the Baidu Map API.

## Tools

1. `map_geocode`
   - 地理编码服务
   - Input: 
     - `address` (string): 待解析的地址。最多支持84个字节。
          可以输入两种样式的值，分别是
          1、标准的结构化地址信息，如北京市海淀区上地十街十号【推荐，地址结构越完整，解析精度越高】
          2、支持“*路与*路交叉口”描述方式，如北一环路和阜阳路的交叉路口
          第二种方式并不总是有返回结果，只有当地址库中存在该地址描述时才有返回。
   - Returns: 
     - `location`: { lat: number, lng: number } 
     - `precise`: number 
     - `confidence`: number 
     - `comprehension`: number 
     - `level`: string 

2. `map_reverse_geocode`
   - 全球逆地理编码
   - Inputs:
     - `latitude` (number)
     - `longitude` (number)
   - Returns:
     - `place_id`: string;
     - `location`: { lng: number, lat: number }
     - `formatted_address`: string
     - `formatted_address_poi`: string
     - `business`: string
     - `business_info`: Array of {
       - `name`: string
       - `location`: { lng: number, lat: number }
       - `adcode`: number
       - `distance`: number
       - `direction`: string
     }
     - `addressComponent`: {
       - `country`: string
       - `province`: string
       - `city`: string
       - `district`: string
       - `street`: string
       - `street_number`: string
       - (and other detailed address components)
     }
     - `pois`: Array of POI information
     - `roads`: Array of nearby roads
     - `poiRegions`: Array of POI regions
     - `sematic_description`: string
     - `cityCode`: number

3. `map_search_places`
   - 地点检索服务（包括城市检索、圆形区域检索、多边形区域检索）
   - Inputs:
     - `query` (string): 检索关键字
     - `region` (string, 可选): 检索行政区划区域，如"北京"
     - `bounds` (string, 可选): 检索多边形区域，格式如"38.76623,116.43213,39.54321,116.46773"
     - `location` (string, 可选): 圆形区域检索中心点，格式如"39.915,116.404"
     注意：region、bounds、location 三个参数必须且只能选择其中一个
   - Returns:
     - `result_type`: string 
     - `query_type`: string
     - `places`: Array of {
       - `name`: string 
       - `location`: { lat: number, lng: number } 
       - `address`: string 
       - `province`: string 
       - `city`: string 
       - `area`: string 
       - `street_id`: string 
       - `telephone`: string 
       - `detail`: number 
       - `uid`: string 
     }

4. `map_place_details`
   - 地点详情检索服务
   - Inputs:
     - `uid` (string): poi的uid
     - `scope` (string, 可选): 检索结果详细程度
       - 1 或空: 返回基本信息
       - 2: 返回检索POI详细信息
   - Returns:
     基本信息 (scope=1):
     - `uid`: string
     - `street_id`: string
     - `name`: string
     - `location`: { lng: number, lat: number }
     - `address`: string
     - `province`: string
     - `city`: string
     - `area`: string
     - `detail`: number

     详细信息 (scope=2):
     包含基本信息，并额外返回：
     - `detail_info`: {
       - `tag`: string
       - `navi_location`: { lng: number, lat: number }
       - `new_catalog`: string
       - `shop_hours`: string
       - `detail_url`: string
       - `type`: string
       - `overall_rating`: string
       - `image_num`: string
       - `comment_num`: string
       - `content_tag`: string 
     }

5. `map_distance_matrix`
   - 计算多个出发地和目的地的距离和路线用时
   - Inputs:
     - `origins` (string[])
     - `destinations` (string[])
     - `mode` (optional): "driving" | "walking" | "riding" | "motorcycle"
   - Returns: distances and durations matrix

6. `map_directions`
   - 路线规划服务
   - Inputs:
     - `origin` (string)
     - `destination` (string)
     - `mode` (optional): "driving" | "walking" | "riding" | "transit"
   - Returns: route details with steps, distance, duration
7. `map_weather`
   - 通过行政区划代码查询实时天气信息及未来5天天气预报
   - Input: `districtId` (string)
   - Returns: location, now, forecasts

8. `map_ip_location`
   - 根据IP定位来获取位置
   - Input: `ip` (string)
   - Returns: formatted_address, address_detail, point

## Setup

### API Key
Get a Baidu Map API key by following the instructions [here](https://lbsyun.baidu.com/faq/search?id=299&title=677).

### Usage with Claude Desktop

Add the following to your `claude_desktop_config.json`:

### NPX

```json
{
  "mcpServers": {
    "baidu-map": {
      "command": "npx",
      "args": [
        "-y",
        "@baidumap/mcp-server-baidu-map"
      ],
      "env": {
        "BAIDU_MAP_API_KEY": "<YOUR_API_KEY>"
      }
    }
  }
}
```

## License

This MCP server is licensed under the MIT License. This means you are free to use, modify, and distribute the software, subject to the terms and conditions of the MIT License. For more details, please see the LICENSE file in the project repository.
