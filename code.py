import spotipy
from spotipy.oauth2 import SpotifyOAuth
import requests
import json
import random
from datetime import datetime

# следующие 3 переменные брать на https://developer.spotify.com/dashboard
client_id = "client_id"
client_secret = "client_secret"
redirect_uri = "http://localhost:8888"  # ставьте свой порт или линк, у меня прописан такой
# взять ключ здесь: https://openrouter.ai/settings/keys
api_key = "api_key"
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=client_id,
                                               client_secret=client_secret,
                                               redirect_uri=redirect_uri,
                                               scope="user-library-read playlist-modify-public"))


def get_random_saved_tracks(limit=50):
    print("получаем ваши сохраненные треки...")
    total_tracks = sp.current_user_saved_tracks(limit=1)['total']
    all_indices = list(range(total_tracks))
    random.shuffle(all_indices)
    selected_indices = all_indices[:limit]
    random_tracks = []
    for i in range(0, len(selected_indices), 20):
        batch_indices = selected_indices[i:i + 20]
        for offset in batch_indices:
            track = sp.current_user_saved_tracks(limit=1, offset=offset)['items'][0]['track']
            random_tracks.append({
                'name': track['name'],
                'artist': track['artists'][0]['name'],
                'id': track['id']
            })
    print(f"получено {len(random_tracks)} случайных треков")
    return random_tracks


def ask_gemini_for_recommendations(tracks):
    print("запрашиваем рекомендации у ии...")
    tracks_text = "\n".join([f"- {t['name']} от {t['artist']}" for t in tracks])
    prompt = f"""ты - музыкальный эксперт. на основе этих {len(tracks)} песен порекомендуй 25 похожих.

    критерии:
    1.отвечай ТОЛЬКО списком песен
    2.используй ТОЛЬКО этот формат: Исполнитель - Название песни
    3.каждая песня должна быть на новой строке
    4.рекомендации должны быть разнообразными, но похожими по стилю на предоставленные треки
    5.не добавляй никакого дополнительного текста, только список песен
    6.НИКАКИХ ОСТАЛЬНЫХ СИМВОЛОВ, только формат из 2 критерия
    
    вот мои любимые треки:
    {tracks_text}"""
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        data=json.dumps({
            "model": "google/gemini-2.0-flash-thinking-exp:free",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0,
            "max_tokens": 10000
        })
    )
    return response.json()['choices'][0]['message']['content']


def parse_recommendations(recommendations_text):
    parsed_recommendations = []
    for line in recommendations_text.split('\n'):
        line = line.strip()
        if '-' in line:
            artist, song = line.split('-', 1)
            parsed_recommendations.append({
                'artist': artist.strip(),
                'song': song.strip()
            })
    return parsed_recommendations


def search_and_create_playlist(recommendations):
    print("создаём новый плейлист...")
    user_id = sp.current_user()['id']
    playlist_name = f"Плейлист ИИ созданный {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    playlist = sp.user_playlist_create(user_id, playlist_name, public=False)
    track_ids = []
    parsed_recs = parse_recommendations(recommendations)
    print("ищем треки в Spotify...")
    for rec in parsed_recs:
        try:
            search_query = f"artist:{rec['artist']} track:{rec['song']}"
            results = sp.search(q=search_query, type='track', limit=1)
            if results['tracks']['items']:
                track_id = results['tracks']['items'][0]['id']
                track_ids.append(track_id)
                print(f"найден трек: {rec['artist']} - {rec['song']}")
            else:
                print(f"не найден трек: {rec['artist']} - {rec['song']}")
        except Exception as e:
            print(f"ошибка при поиске трека {rec}: {str(e)}")
    if track_ids:
        sp.playlist_add_items(playlist['id'], track_ids)
        print(f"добавлено {len(track_ids)} треков в плейлист!")
    else:
        print("не найдено треков для добавления в плейлист(")
    return playlist['external_urls']['spotify']


def main():
    saved_tracks = get_random_saved_tracks(50)
    recommendations_text = ask_gemini_for_recommendations(saved_tracks)
    print("\nрекомендации от ИИ:")
    print(recommendations_text)
    playlist_url = search_and_create_playlist(recommendations_text)
    print(f"\nсоздан плейлист: {playlist_url}")

if __name__ == "__main__":
    main()
