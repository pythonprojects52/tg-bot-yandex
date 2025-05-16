import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import math
import numpy as np
import osmnx as ox
import networkx as nx
import folium
from geopy.geocoders import Nominatim
import tempfile
import os
import time
from datetime import datetime
from math import sqrt

# Настройки логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = "7940046159:AAGkKCjcwwpUpSQoUfnR3EnTWzBW6ZMib2g"

# Настройки маршрутизации
CITY_NAME = "Уфа, Россия"
GRAPH_FILENAME = "ufa_graph.graphml"
USER_AGENT = "ufa_route_planner_v9"
AVG_WALKING_SPEED = 5  # км/ч
AVG_DRIVING_SPEED = 50  # км/ч
TRACKING_INTERVAL = 30  # секунд между обновлениями

# Данные по районам Уфы и интересным местам
DISTRICTS = {
    "Кировский": {
        "bounds": {"lat_min": 54.73, "lat_max": 54.80, "lon_min": 55.90, "lon_max": 56.00},
        "places": {
            "Монумент Дружбы": {
                "desc": "Крупнейший парк города с мемориальным комплексом",
                "coords": (54.711787, 55.963509)
            },
            "Собор Рождества Богородицы": {
                "desc": "Главный театр Башкортостана, основан в 1938 году",
                "coords": (54.727084, 55.972902)
            },
            "Сад им. Салавата Юлаева": {
                "desc": "Известный общественный сад с видом на р.Белую",
                "coords": (54.7123, 55.9523)
            }
        }
    },
    "Ленинский": {
        "bounds": {"lat_min": 54.7380, "lat_max": 54.7950, "lon_min": 55.9170, "lon_max": 55.9650},
        "places": {
            "Парк Якутова": {
                "desc": "Старейший парк Уфы с аттракционами и кафе",
                "coords": (54.7356, 55.9789)
            },
            "Гостиный двор": {
                "desc": "Торгово-развлекательный комплекс в историческом здании",
                "coords": (54.7265, 55.9479)
            },
            "Двор Довлатова": {
                "desc": "Арт-пространство, вдохновлённое писателем С.Довлатовым.",
                "coords": (54.7278, 55.9392)
            }
        }
    },
    "Советский": {
        "bounds": {"lat_min": 54.7430, "lat_max": 54.7950, "lon_min": 55.8830, "lon_max": 55.9250},
        "places": {
            "Лесопарк им. лесоводов": {
                "desc": "Один из самых больших парков в Уфе",
                "coords": (54.7325, 56.0146)
            },
            "ТЦ Мир": {
                "desc": "Самый большой ТЦ в Уфе",
                "coords": (54.7416, 55.9874)
            },
            "Уфа-Арена": {
                "desc": "Домашний спортивно-концертный комплекс российского ХК «Салават Юлаев»",
                "coords": (54.7390, 55.9568)
            }
        }
    },
    "Дёмский": {
        "bounds": {"lat_min": 54.66, "lat_max": 54.75, "lon_min": 55.78, "lon_max": 55.92},
        "places": {
            "Сквер микрорайона «Яркий»": {
                "desc": "Тенистое место для вечерних прогулок",
                "coords": (54.7008, 55.8576)
            },
            "Аллея сказок": {
                "desc": "Музей под открытым небом, наполненный героями сказок",
                "coords": (54.7026, 55.8319)
            },
            "Дёмский парк": {
                "desc": "Один из первых парков культуры и отдыха в одноимённом районе",
                "coords": (54.7034, 55.8281)
            }
        }
    },
    "Октябрьский": {
        "bounds": {"lat_min": 54.57, "lat_max": 54.67, "lon_min": 56.06, "lon_max": 56.16},
        "places": {
            "Кашкадан": {
                "desc": "Озеро-старица реки Уфы, находящееся посреди любимого многими парка",
                "coords": (54.7744, 56.0599)
            },
            "Волшебный Мир": {
                "desc": "Просторный парк с самыми разными аттракционами",
                "coords": (54.7739, 56.0215)
            },
            "ТЦ Планета": {
                "desc": "Центр торговли и развлечений, торговая галерея которого насчитывает около 200 магазинов",
                "coords": (54.7575, 56.0340)
            }
        }
    },
    "Калининский": {
        "bounds": {"lat_min": 54.65, "lat_max": 54.88, "lon_min": 56.04, "lon_max": 56.26},
        "places": {
            "Первомайский парк": {
                "desc": "Один из красивейших парков города по мнению многих резидентов",
                "coords": (54.8063, 56.1179)
            },
            "ТЦ Башкирия": {
                "desc": "Современный торговый центр с множеством магазинов и ресторанов",
                "coords": (54.7414, 56.0270)
            },
            "Олимпик-парк": {
                "desc": "Один из двух горнолыжных курортов Уфы, находящийся в живописном парке",
                "coords": (54.7375, 56.0296)
            }
        }
    },
    "Орджоникидзевский": {
        "bounds": {"lat_min": 54.77, "lat_max": 54.95, "lon_min": 56.01, "lon_max": 56.27},
        "places": {
            "Дворец Молодёжи": {
                "desc": "Одна из крупнейших концертных площадок в Уфе",
                "coords": (54.8199, 56.0695)
            },
            "Парк Нефтехимиков": {
                "desc": "Популярное место для прогулок и занятий спортом, к которому примыкает сквер Победы",
                "coords": (54.8169, 56.0883)
            },
            "парк Победы": {
                "desc": "Мемориальный парк в честь Победы в Великой Отечественной войне",
                "coords": (54.8218, 56.0571)
            }
        }
    },
}
# Класс для управления маршрутами
class RouteManager:
    def __init__(self):
    # Словарь для хранения активных отслеживаний
        self.active_tracks = {}
        # Загрузка графа дорог
        self.graph = self._load_graph()
        # Инициализация геокодера
        self.geolocator = Nominatim(user_agent=USER_AGENT)
        
    def _load_graph(self):
        if os.path.exists(GRAPH_FILENAME):
            logger.info("Загружаем граф дорог из файла...")
            return ox.load_graphml(GRAPH_FILENAME)
        else:
            logger.info("Создаем новый граф дорог (это может занять несколько минут)...")
            graph = ox.graph_from_place(CITY_NAME, network_type='drive')
            ox.save_graphml(graph, GRAPH_FILENAME)
            return graph
    
    def _get_nearest_node(self, point):
        try:
            return ox.distance.nearest_nodes(self.graph, point[1], point[0])
        except Exception as e:
            logger.error(f"Ошибка поиска узла: {e}")
            return None
    
    def create_route_map(self, start_point, end_point, start_name="Вы", end_name="Цель"):
        try:
            start_node = self._get_nearest_node(start_point)
            end_node = self._get_nearest_node(end_point)
            
            if not start_node or not end_node:
                return None, None
                
            route = nx.shortest_path(self.graph, start_node, end_node, weight='length')
            
            # Рассчитываем параметры маршрута
            length = sum(self.graph.edges[u, v, 0]['length'] for u, v in zip(route[:-1], route[1:])) / 1000
            walk_time = length / AVG_WALKING_SPEED * 60
            drive_time = length / AVG_DRIVING_SPEED * 60
            
            # Создаем карту
            m = folium.Map(
                location=start_point,
                zoom_start=14,
                tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                attr='© OpenStreetMap contributors'
            )
            
            # Добавляем маркеры
            folium.Marker(
                start_point,
                popup=start_name,
                icon=folium.Icon(color='green', icon='user', prefix='fa')
            ).add_to(m)
            
            folium.Marker(
                end_point,
                popup=end_name,
                icon=folium.Icon(color='red', icon='flag', prefix='fa')
            ).add_to(m)
            
            # Добавляем линию маршрута
            route_points = [(self.graph.nodes[n]['y'], self.graph.nodes[n]['x']) for n in route]
            folium.PolyLine(
                route_points,
                color='blue',
                weight=5,
                opacity=0.7,
                popup=f"Расстояние: {length:.2f} км<br>Пешком: {walk_time:.1f} мин<br>На машине: {drive_time:.1f} мин"
            ).add_to(m)
            
            # Информационная панель
            info_html = f"""
            <div style="
                position: fixed; bottom: 50px; left: 50px; 
                width: 300px; z-index:9999; font-size:14px;
                background-color:white; padding:10px;
                border-radius:5px; box-shadow:0 0 5px grey;
            ">
                <b>Маршрут от {start_name} до {end_name}</b><br>
                Расстояние: {length:.2f} км<br>
                Пешком: {walk_time:.1f} мин<br>
                На машине: {drive_time:.1f} мин<br>
                <small>Обновлено: {datetime.now().strftime('%H:%M:%S')}</small>
            </div>
            """
            m.get_root().html.add_child(folium.Element(info_html))
            
            # Сохраняем карту
            with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
                m.save(f.name)
                return f.name, {
                    'distance': round(length, 2),
                    'walk_time': round(walk_time, 1),
                    'drive_time': round(drive_time, 1),
                    'route_points': route_points
                }
                
        except Exception as e:
            logger.error(f"Ошибка построения маршрута: {e}")
            return None, None
    
    def start_tracking(self, chat_id, destination_point, destination_name):
        self.active_tracks[chat_id] = {
            'destination': destination_point,
            'destination_name': destination_name,
            'last_update': time.time()
        }
    
    def update_position(self, chat_id, position):
        if chat_id in self.active_tracks:
            track = self.active_tracks[chat_id]
            map_path, stats = self.create_route_map(
                position,
                track['destination'],
                "Ваше местоположение",
                track['destination_name']
            )
            track['last_update'] = time.time()
            return map_path, stats
        return None, None
    
    def stop_tracking(self, chat_id):
        if chat_id in self.active_tracks:
            del self.active_tracks[chat_id]

# Инициализация менеджера маршрутов
route_manager = RouteManager()

def distances(lat1, lon1, lat2, lon2):
    """Расчет расстояния между двумя точками на Земле"""
    lat1_rad = np.radians(lat1)
    lon1_rad = np.radians(lon1)
    lat2_rad = np.radians(lat2)
    lon2_rad = np.radians(lon2)
    
    x_diff = (lon2_rad - lon1_rad) * np.cos((lat1_rad + lat2_rad) / 2)
    y_diff = lat2_rad - lat1_rad
    return np.sqrt(x_diff**2 + y_diff**2) * 6371

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[KeyboardButton("Куда отправимся?")]]
    await update.message.reply_text(
        "Привет! Я помогу найти интересные места в Уфе и построить маршруты.\n"
        "Нажми 'Куда отправимся?' и поделись своей геолокацией.",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def request_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[KeyboardButton("Отправить геолокацию 📍", request_location=True)]]
    await update.message.reply_text(
        "Пожалуйста, поделись своим местоположением:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    location = update.message.location
    logger.info(f"Получена геолокация: {location.latitude}, {location.longitude}")

    # Проверка активного отслеживания
    if update.message.chat_id in route_manager.active_tracks:
        map_path, stats = route_manager.update_position(
            update.message.chat_id,
            (location.latitude, location.longitude)
        )
        
        if map_path:
            try:
                await update.message.reply_document(
                    document=open(map_path, 'rb'),
                    caption=f"Обновленный маршрут\n"
                           f"Осталось: {stats['distance']} км\n"
                           f"Пешком: {stats['walk_time']} мин\n"
                           f"На машине: {stats['drive_time']} мин"
                )
                os.unlink(map_path)
            except Exception as e:
                logger.error(f"Ошибка отправки карты: {e}")
        return

    # Обычная обработка геолокации
    district = get_district(location.latitude, location.longitude)
    context.user_data['user_location'] = (location.latitude, location.longitude)

    if district:
        keyboard = [
            [KeyboardButton("Показать места рядом")],
            [KeyboardButton("Построить маршрут")]
        ]
        await update.message.reply_text(
            f"Вы в {district} районе. Что вас интересует?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
    else:
        await update.message.reply_text("Вы за пределами Уфы")

async def show_district_places(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if 'user_location' not in context.user_data:
        await update.message.reply_text("Сначала отправьте вашу геолокацию")
        return
        
    user_loc = context.user_data['user_location']
    district = get_district(user_loc[0], user_loc[1])
    
    if not district or district not in DISTRICTS:
        await update.message.reply_text("Не удалось определить ваш район")
        return
        
    district_data = DISTRICTS[district]
    user_lat, user_lon = user_loc
    
    places_text = "\n\n".join(
        [f"<b>{name}</b>\n{data['desc']}\n"
         f"Расстояние: {distances(user_lat, user_lon, *data['coords']):.2f} км"
         for name, data in district_data["places"].items()]
    )

    keyboard = [[KeyboardButton(name)] for name in district_data["places"]] + [
        [KeyboardButton("Назад")]
    ]
    
    await update.message.reply_text(
        f"<b>Места в {district} районе:</b>\n\n{places_text}",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def handle_place_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    place_name = update.message.text
    user_loc = context.user_data.get('user_location')
    
    if not user_loc:
        await update.message.reply_text("Сначала отправьте вашу геолокацию")
        return
    
    # Поиск места в базе
    for district in DISTRICTS.values():
        if place_name in district["places"]:
            place_data = district["places"][place_name]
            destination = place_data["coords"]
            
            # Строим маршрут
            map_path, stats = route_manager.create_route_map(
                user_loc,
                destination,
                "Ваше местоположение",
                place_name
            )
            
            if map_path:
                try:
                    await update.message.reply_document(
                        document=open(map_path, 'rb'),
                        caption=f"Маршрут до {place_name}\n"
                               f"Расстояние: {stats['distance']} км\n"
                               f"Пешком: {stats['walk_time']} мин\n"
                               f"На машине: {stats['drive_time']} мин"
                    )
                    os.unlink(map_path)
                    
                    # Предлагаем отслеживание
                    keyboard = [
                        [KeyboardButton(f"Отслеживать маршрут до {place_name}")],
                        [KeyboardButton("Назад")]
                    ]
                    await update.message.reply_text(
                        "Хотите включить отслеживание маршрута?",
                        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                    )
                    
                    # Сохраняем данные о маршруте
                    context.user_data['current_destination'] = destination
                    context.user_data['current_destination_name'] = place_name
                except Exception as e:
                    logger.error(f"Ошибка отправки карты: {e}")
            return
    
    await update.message.reply_text("Место не найдено")

async def start_tracking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'current_destination' in context.user_data:
        route_manager.start_tracking(
            update.message.chat_id,
            context.user_data['current_destination'],
            context.user_data['current_destination_name']
        )
        
        await update.message.reply_text(
            "Отслеживание маршрута начато! Отправляйте свою геопозицию "
            f"каждые {TRACKING_INTERVAL} секунд для обновления.\n\n"
            "Для остановки нажмите /stop_tracking",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("Остановить отслеживание")]],
                resize_keyboard=True
            )
        )
    else:
        await update.message.reply_text("Сначала выберите место назначения")

async def stop_tracking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    route_manager.stop_tracking(update.message.chat_id)
    await update.message.reply_text(
        "Отслеживание остановлено.",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("Куда отправимся?")]],
            resize_keyboard=True
        )
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "Этот бот помогает находить интересные места в Уфе и строить маршруты.\n\n"
        "Доступные команды:\n"
        "/start - начать работу\n"
        "/help - получить справку\n"
        "/stop_tracking - остановить отслеживание\n\n"
        "Как использовать:\n"
        "1. Отправьте свою геолокацию\n"
        "2. Выберите место назначения\n"
        "3. Включите отслеживание (по желанию)\n"
        "4. Отправляйте геопозицию для обновления маршрута"
    )
    await update.message.reply_text(help_text)

def get_district(lat: float, lon: float) -> str:
    for district_name, data in DISTRICTS.items():
        bounds = data["bounds"]
        if (bounds["lat_min"] <= lat <= bounds["lat_max"] and
                bounds["lon_min"] <= lon <= bounds["lon_max"]):
            return district_name
    return None

def main() -> None:
    application = Application.builder().token(TOKEN).build()

    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stop_tracking", stop_tracking))
    
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'Куда отправимся\?'), request_location))
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))
    
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'Показать места рядом'), show_district_places))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'Построить маршрут'), show_district_places))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'Отслеживать маршрут до .+'), start_tracking))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'Остановить отслеживание'), stop_tracking))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'Назад'), start))
    
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & 
        ~filters.Regex(r'Куда отправимся\?') & 
        ~filters.Regex(r'Показать места рядом') &
        ~filters.Regex(r'Построить маршрут') &
        ~filters.Regex(r'Отслеживать маршрут до .+') &
        ~filters.Regex(r'Остановить отслеживание') &
        ~filters.Regex(r'Назад'),
        handle_place_selection
    ))

    logger.info("Бот запущен с функцией отслеживания маршрутов...")
    application.run_polling()

if __name__ == "__main__":
    main()
#   pip install python-telegram-bot
#   pip install numpy
#   pip install osmnx
#   pip install osmnx
#   pip install networkx
#   pip install folium
#   pip install geopy
  
   
