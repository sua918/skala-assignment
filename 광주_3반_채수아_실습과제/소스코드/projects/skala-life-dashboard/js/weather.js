const URL = 'https://api.open-meteo.com/v1/forecast?latitude=35.1396&longitude=126.7937&current=temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m';

function advice(current) {
  const rain = current.precipitation > 0 || [51,53,55,61,63,65,80,81,82].includes(current.weather_code);
  const clothes = current.temperature_2m < 10 ? '따뜻한 겉옷을 챙기세요.' : current.temperature_2m > 27 ? '가볍고 시원한 옷이 좋아요.' : '가벼운 겉옷이 알맞아요.';
  return { text: `${rain ? '우산이 필요한 날이에요. ' : ''}${clothes}`, rain };
}

export async function getWeather() {
  const response = await fetch(URL);
  if (!response.ok) throw new Error('날씨 요청 실패');
  const current = (await response.json()).current;
  return { ...current, ...advice(current), fetchedAt: Date.now() };
}

