#!/usr/bin/env node

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from "@modelcontextprotocol/sdk/types.js";
import fetch from "node-fetch";

// Response interfaces
interface BaiduMapResponse {
  status: number;
  msg?: string;
  message?: string;
}

interface GeocodeResponse extends BaiduMapResponse {
  result: {
    location: {
      lat: number;
      lng: number;
    }
    precise: number;
    confidence: number;
    comprehension: number;
    level: string;
  };
}

interface ReverseGeocodeResponse extends BaiduMapResponse {
  result: {
    location: {
      lng: number;
      lat: number;
    };
    formatted_address: string;
    edz: {
      name: string;
    };
    business: string;
    business_info: Array<{
      name: string;
      location: {
        lng: number;
        lat: number;
      };
      adcode: number;
      distance: number;
      direction: string;
    }>;
    addressComponent: {
      country: string;
      country_code: number;
      country_code_iso: string;
      country_code_iso2: string;
      province: string;
      city: string;
      city_level: number;
      district: string;
      town: string;
      town_code: string;
      distance: string;
      direction: string;
      adcode: string;
      street: string;
      street_number: string;
    };
    pois: any[];
    roads: any[];
    poiRegions: any[];
    sematic_description: string;
    formatted_address_poi: string;
    cityCode: number;
  };
}

interface PlacesSearchResponse extends BaiduMapResponse {
  result_type?: string;
  query_type?: string;
  results?: Array<{
    name: string;
    location: {
      lat: number;
      lng: number;
    };
    address: string;
    province: string;
    city: string;
    area: string;
    street_id?: string;
    telephone?: string;
    detail: number;
    uid: string;
  }>;
  // region 参数时的返回结构
  result?: Array<{
    name: string;
    location: {
      lat: number;
      lng: number;
    };
    address: string;
    province: string;
    city: string;
    area: string;
    street_id?: string;
    telephone?: string;
    detail: number;
    uid: string;
  }>;
}

// PlaceDetails Base Response
interface PlaceDetailsBaseResponse extends BaiduMapResponse {
  result: {
    uid: string;
    street_id: string;
    name: string;
    location: {
      lng: number;
      lat: number;
    };
    address: string;
    province: string;
    city: string;
    area: string;
    detail: number;
  };
}
// scope=2 时的详细信息
interface PlaceDetailsFullResponse extends BaiduMapResponse {
  result: PlaceDetailsBaseResponse['result'] & {
    detail_info: {
      tag: string;
      navi_location: {
        lng: number;
        lat: number;
      };
      new_catalog: string;
      shop_hours: string;
      detail_url: string;
      type: string;
      overall_rating: string;
      image_num: string;
      comment_num: string;
      content_tag: string;
    };
  };
}

type PlaceDetailsResponse = PlaceDetailsBaseResponse | PlaceDetailsFullResponse;

interface DistanceMatrixResponse extends BaiduMapResponse {
  result: Array<{
    distance: {
      text: string;
      value: string;
    };
    duration: {
      text: string;
      value: string;
    };
  }>;
}

interface DirectionsResponse extends BaiduMapResponse {
  result: {
    routes: Array<{
      distance: number;
      duration: number;
      steps: Array<{
        instruction: string;
      }>
    }>;
  };
}

interface WeatherResponse extends BaiduMapResponse {
  result: {
    location: {
      province: string,
      city: string,
      name: string,
    },
    now: {
      text: string,
      temp: number,
      feels_like: number,
      rh: number,
      wind_class: string,
      wind_dir: string,
      uptime: number,
    },
    forecasts: Array<{
      text_day: string,
      text_night: string,
      high: number,
      low: number,
      wc_day: string,
      wd_day: string,
      wc_night: string,
      wd_night: string,
      date: string,
      week: string,
    }>
  }
}

interface IPLocationResponse extends BaiduMapResponse {
  address: string,
  content: {
    address: string,
    address_detail: {
      city: string,
      city_code: number,
      province: string
    },
    point: {
      x: string,
      y: string,
    }
  }
}

function getApiKey(): string {
    const apiKey = process.env.BAIDU_MAP_API_KEY;
    if (!apiKey) {
      console.error("BAIDU_MAP_API_KEY environment variable is not set");
      process.exit(1);
    }
    return apiKey;
  }

const BAIDU_MAP_API_KEY = getApiKey();

// Tool definitions
const GEOCODE_TOOL: Tool = {
    name: "map_geocode",
    description: "地理编码服务",
    inputSchema: {
      type: "object",
      properties: {
        address: {
          type: "string",
          description: "待解析的地址（最多支持84个字节。可以输入两种样式的值，分别是：1、标准的结构化地址信息，如北京市海淀区上地十街十号【推荐，地址结构越完整，解析精度越高】2、支持“*路与*路交叉口”描述方式，如北一环路和阜阳路的交叉路口第二种方式并不总是有返回结果，只有当地址库中存在该地址描述时才有返回。）"
        }
      },
      required: ["address"]
    }
  };

const REVERSE_GEOCODE_TOOL: Tool = {
  name: "map_reverse_geocode",
  description: "全球逆地理编码",
  inputSchema: {
    type: "object",
    properties: {
      latitude: {
        type: "number",
        description: "Latitude coordinate"
      },
      longitude: {
        type: "number",
        description: "Longitude coordinate"
      }
    },
    required: ["latitude", "longitude"]
  }
};

const SEARCH_PLACES_TOOL: Tool = {
  name: "map_search_places",
  description: "地点检索服务（包括城市检索、圆形区域检索、多边形区域检索）",
  inputSchema: {
    type: "object",
    properties: {
      query: {
        type: "string",
        description: "检索关键字"
      },
      region: {
        type: "string",
        description: "检索行政区划区域"
      },
      bounds: {
        type: "string",
        description: "检索多边形区域"
      },
      location: {
        type: "string",
        description: "圆形区域检索中心点，不支持多个点"
      },
    },
    required: ["query"],
  }
};


const PLACE_DETAILS_TOOL: Tool = {
  name: "map_place_details",
  description: "地点详情检索服务",
  inputSchema: {
    type: "object",
    properties: {
      uid: {
        type: "string",
        description: "poi的uid"
      },
      scope: {
        type: "string",
        description: "检索结果详细程度。取值为1 或空，则返回基本信息；取值为2，返回检索POI详细信息"
      }
    },
    required: ["uid"]
  }
};


const DISTANCE_MATRIX_TOOL: Tool = {
  name: "map_distance_matrix",
  description: "计算多个出发地和目的地的距离和路线用时",
  inputSchema: {
    type: "object",
    properties: {
      origins: {
        type: "array",
        items: { type: "string" },
        description: "起点的纬度,经度。"
      },
      destinations: {
        type: "array",
        items: { type: "string" },
        description: "终点的纬度,经度。"
      },
      mode: {
        type: "string",
        description: "路线类型，可选值：driving（驾车）、walking（步行）、riding（骑行）、motorcycle（摩托车）",
        enum: ["driving", "walking", "riding", "motorcycle"]
      }
    },
    required: ["origins", "destinations"]
  }
};

const DIRECTIONS_TOOL: Tool = {
  name: "map_directions",
  description: "路线规划服务， 计算出发地到目的地的距离、路线用时、路线方案",
  inputSchema: {
    type: "object",
    properties: {
      origin: {
        type: "string",
        description: "起点经纬度，格式为：纬度,经度；小数点后不超过6位，40.056878,116.30815"
      },
      destination: {
        type: "string",
        description: "终点经纬度，格式为：纬度,经度；小数点后不超过6位，40.056878,116.30815"
      },
      mode: {
        type: "string",
        description: "路线规划类型，可选值：driving（驾车）、walking（步行）、riding（骑行）、transit（公交）",
        enum: ["driving", "walking", "riding", "transit"]
      }
    },
    required: ["origin", "destination"]
  }
};

const WEATHER_TOOL: Tool = {
  name: "map_weather",
  description: '通过行政区划代码获取实时天气信息和未来5天天气预报',
  inputSchema: {
    type: "object",
    properties: {
      districtId: {
        type: "string",
        description: "行政区划代码（适用于区、县级别）"
      }
    },
    required: ["districtId"],
  }
}

const IP_LOCATION_TOOL: Tool ={
  name: "map_ip_location",
  description: "通过IP地址获取位置信息",
  inputSchema: {
    type: "object",
    properties: {
      ip: {
        type: "string",
        description: "IP地址",
      }
    },
    required: ["ip"],
  }
}

const MAPS_TOOLS = [
  GEOCODE_TOOL,
  REVERSE_GEOCODE_TOOL,
  SEARCH_PLACES_TOOL,
  PLACE_DETAILS_TOOL,
  DISTANCE_MATRIX_TOOL,
  DIRECTIONS_TOOL,
  WEATHER_TOOL,
  IP_LOCATION_TOOL,
] as const;

// API handlers
async function handleGeocode(address: string) {
  const url = new URL("https://api.map.baidu.com/geocoding/v3/");
  url.searchParams.append("address", address);
  url.searchParams.append("ak", BAIDU_MAP_API_KEY);
  url.searchParams.append("output", "json");
  url.searchParams.append("from", "node_mcp");

  const response = await fetch(url.toString());
  const data = await response.json() as GeocodeResponse;
  if (data.status !== 0) {
    return {
      content: [{
        type: "text",
        text: `Geocoding failed: ${data.message || data.status}`
      }],
      isError: true
    };
  }

  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        location: data.result.location,
        precise: data.result.precise,
        confidence: data.result.confidence,
        comprehension: data.result.comprehension,
        level: data.result.level
      }, null, 2)
    }],
    isError: false
  };
}

async function handleReverseGeocode(latitude: number, longitude: number) {
  const url = new URL("https://api.map.baidu.com/reverse_geocoding/v3/");
  url.searchParams.append("location", `${latitude},${longitude}`);
  url.searchParams.append("extensions_poi", "1");
  url.searchParams.append("ak", BAIDU_MAP_API_KEY);
  url.searchParams.append("output", "json");
  url.searchParams.append("from", "node_mcp");

  const response = await fetch(url.toString());
  const data = await response.json() as ReverseGeocodeResponse;

  if (data.status !== 0) {
    return {
      content: [{
        type: "text",
        text: `Reverse geocoding failed: ${data.message || data.status}`
      }],
      isError: true
    };
  }

  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        place_id: data.result.pois[0] ? data.result.pois[0].uid : null,
        location: data.result.location,
        formatted_address: data.result.formatted_address,
        formatted_address_poi: data.result.formatted_address_poi,
        business: data.result.business,
        business_info: data.result.business_info,
        addressComponent: data.result.addressComponent,
        edz: data.result.edz,
        pois: data.result.pois,
        roads: data.result.roads,
        poiRegions: data.result.poiRegions,
        sematic_description: data.result.sematic_description,
        cityCode: data.result.cityCode
      }, null, 2)
    }],
    isError: false
  };
}

async function handlePlaceSearch(
  query: string,
  region?: string,
  bounds?: string,
  location?: string
) {
  const url = new URL("https://api.map.baidu.com/place/v2/search");
  url.searchParams.append("query", query);
  url.searchParams.append("ak", BAIDU_MAP_API_KEY);
  url.searchParams.append("output", "json");
  url.searchParams.append("from", "node_mcp");
  if (region) {
    url.searchParams.append("region", region);
  }
  if (bounds) {
    url.searchParams.append("bounds", bounds);
  }
  if (location) {
    url.searchParams.append("location", location);
  }

  const response = await fetch(url.toString());
  const data = await response.json() as PlacesSearchResponse;
  if (data.status !== 0) {
    return {
      content: [{
        type: "text",
        text: `Place search failed: ${data.message || data.status}`
      }],
      isError: true
    };
  }

  // 处理不同参数返回的数据结构
  const places = data.results || data.result || [];
  
  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        result_type: data.result_type,
        query_type: data.query_type,
        results: places.map((place) => ({
          name: place.name,
          location: place.location,
          address: place.address,
          province: place.province,
          city: place.city,
          area: place.area,
          street_id: place.street_id,
          telephone: place.telephone,
          detail: place.detail,
          uid: place.uid
        }))
      }, null, 2)
    }],
    isError: false
  };
}

async function handlePlaceDetails(uid: string, scope?: string) {
  const url = new URL("https://api.map.baidu.com/place/v2/detail");
  url.searchParams.append("uid", uid);
  url.searchParams.append("ak", BAIDU_MAP_API_KEY);
  url.searchParams.append("output", "json");
  url.searchParams.append("from", "node_mcp");
  if (scope) {
    url.searchParams.append("scope", scope);
  }
  
  const response = await fetch(url.toString());
  const data = await response.json() as PlaceDetailsResponse;

  if (data.status !== 0) {
    return {
      content: [{
        type: "text",
        text: `Place details request failed: ${data.message || data.status}`
      }],
      isError: true
    };
  }

  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        uid: data.result.uid,
        name: data.result.name,
        location: data.result.location,
        address: data.result.address,
        province: data.result.province,
        city: data.result.city,
        area: data.result.area,
        street_id: data.result.street_id,
        detail: data.result.detail,
        ...(('detail_info' in data.result) ? {
          detail_info: data.result.detail_info
        } : {})
      }, null, 2)
    }],
    isError: false
  };
}

async function handleDistanceMatrix(
  origins: string[],
  destinations: string[],
  mode: "driving" | "walking" | "riding" | "motorcycle" = "driving"
) {
  const url = new URL("https://api.map.baidu.com/routematrix/v2/" + mode);
  url.searchParams.append("origins", origins.join("|"));
  url.searchParams.append("destinations", destinations.join("|"));
  url.searchParams.append("ak", BAIDU_MAP_API_KEY);
  url.searchParams.append("output", "json");
  url.searchParams.append("from", "node_mcp");

  const response = await fetch(url.toString());
  const data = await response.json() as DistanceMatrixResponse;

  if (data.status !== 0) {
    return {
      content: [{
        type: "text",
        text: `Distance matrix request failed: ${data.msg || data.status}`
      }],
      isError: true
    };
  }

  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        results: data.result.map((row) => ({
          elements: {
            duration: row.duration,
            distance: row.distance
          }
        }))
      }, null, 2)
    }],
    isError: false
  };
}

async function handleDirections(
  origin: string,
  destination: string,
  mode: "driving" | "walking" | "riding" | "transit" = "driving"
) {
  const url = new URL("https://api.map.baidu.com/directionlite/v1/" + mode);
  url.searchParams.append("origin", origin);
  url.searchParams.append("destination", destination);
  url.searchParams.append("ak", BAIDU_MAP_API_KEY);
  url.searchParams.append("from", "node_mcp");

  const response = await fetch(url.toString());
  const data = await response.json() as DirectionsResponse;

  if (data.status !== 0) {
    return {
      content: [{
        type: "text",
        text: `Directions request failed: ${data.msg || data.status}`
      }],
      isError: true
    };
  }
  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        routes: data.result.routes.map((route) => ({
          distance: route.distance,
          duration: route.duration,
          steps: route.steps.map((step) => ({
            instructions: step.instruction,
          }))
        }))
      }, null, 2)
    }],
    isError: false
  };
}

async function handleWeather(
  districtId: string
) {
  const url = new URL("https://api.map.baidu.com/weather/v1/");
  url.searchParams.append("district_id", districtId);
  url.searchParams.append("data_type", "all");
  url.searchParams.append("coordtype", "bd09ll");
  url.searchParams.append("ak", BAIDU_MAP_API_KEY);
  url.searchParams.append("from", "node_mcp");

  const response = await fetch(url.toString());
  const data = await response.json() as WeatherResponse;

  if (data.status !== 0) {
    return {
      content: [{
        type: 'text',
        text: `Weather searth failed: ${data.message || data.status}`
      }],
      isError: true
    }
  }

  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        location: data.result.location,
        now: data.result.now,
        forecasts: data.result.forecasts,
      }, null, 2)
    }],
    isError: false
  }
}

async function handleIPLocation(
  ip: string,
) {
  const url = new URL("https://api.map.baidu.com/location/ip");
  url.searchParams.append("ip", ip);
  url.searchParams.append("coor", "bd09ll");
  url.searchParams.append("ak", BAIDU_MAP_API_KEY);
  url.searchParams.append("from", "node_mcp");

  const response = await fetch(url.toString());
  const data = await response.json() as IPLocationResponse;

  if (data.status !== 0) {
    return {
      content: [{
        type: 'text',
        text: `IP address searth failed: ${data.message || data.status}`
      }],
      isError: true
    }
  }


  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        formatted_address: data.address,
        address_detail: data.content.address_detail,
        point: data.content.point,
      }, null, 2)
    }],
    isError: false
  }
}

// Server setup
const server = new Server(
  {
    name: "mcp-server/baidu-map",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  },
);

// Set up request handlers
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: MAPS_TOOLS,
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  try {
    switch (request.params.name) {
      case "map_geocode": {
        const { address } = request.params.arguments as { address: string };
        return await handleGeocode(address);
      }

      case "map_reverse_geocode": {
        const { latitude, longitude } = request.params.arguments as {
          latitude: number;
          longitude: number;
        };
        return await handleReverseGeocode(latitude, longitude);
      }

      case "map_search_places": {
        const { query, region, bounds, location } = request.params.arguments as {
          query: string;
          region?: string;
          bounds?: string;
          location?: string;
        };
        return await handlePlaceSearch(query, region, bounds, location);
      }

      case "map_place_details": {
        const { uid, scope } = request.params.arguments as {
          uid: string;
          scope?: string;
        };
        return await handlePlaceDetails(uid, scope);
      }

      case "map_distance_matrix": {
        const { origins, destinations, mode } = request.params.arguments as {
          origins: string[];
          destinations: string[];
          mode?: "driving" | "walking" | "riding" | "motorcycle";
        };
        return await handleDistanceMatrix(origins, destinations, mode);
      }

      case "map_directions": {
        const { origin, destination, mode } = request.params.arguments as {
          origin: string;
          destination: string;
          mode?: "driving" | "walking" | "riding" | "transit";
        };
        return await handleDirections(origin, destination, mode);
      }
      case "map_weather": {
        const {districtId} = request.params.arguments as {
          districtId: string;
        };
        return await handleWeather(districtId);
      }
      case "map_ip_location": {
        const {ip} = request.params.arguments as {
          ip: string;
        };
        return await handleIPLocation(ip);
      }

      default:
        return {
          content: [{
            type: "text",
            text: `Unknown tool: ${request.params.name}`
          }],
          isError: true
        };
    }
  } catch (error) {
    return {
      content: [{
        type: "text",
        text: `Error: ${error instanceof Error ? error.message : String(error)}`
      }],
      isError: true
    };
  }
});

async function runServer() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Baidu Map MCP Server running on stdio");
}

runServer().catch((error) => {
  console.error("Fatal error running server:", error);
  process.exit(1);
});
