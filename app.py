from flask import Flask, flash, render_template, request, jsonify, redirect, url_for, session
from googleapiclient.discovery import build
from pytube import YouTube
from pathlib import Path
import os
import mysql.connector



mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="music_player"
)




app = Flask(__name__)

app.secret_key = os.urandom(24)

# Thay đổi 'YOUR_API_KEY' bằng API key của bạn
API_KEY = 'AIzaSyCmhpDQnXw6O8sR1uqcCsq4E94Okntk8ig'

# Khởi tạo YouTube API
youtube = build('youtube', 'v3', developerKey=API_KEY)


class Song:
    def __init__(self, id, title, artist, thumbnail, songUrl, audioUrl):
   
        self.id = id
        self.title = title
        self.artist = artist
        self.thumbnail = thumbnail
        self.songUrl = songUrl
        self.audioUrl = audioUrl
     
def getInfoSong(id):
    request = youtube.videos().list(part='snippet', id=id).execute()
    songResponse = request['items'][0]['snippet']
    thumbnail_url = songResponse['thumbnails']['medium']['url']
    songUrl = f'https://www.youtube.com/watch?v={id}'

    video = YouTube(songUrl)
    bestAudio = video.streams.filter(only_audio=True).first()
    audioUrl = bestAudio.url
    songInfo = Song(id, songResponse['title'], songResponse['channelTitle'], thumbnail_url, songUrl, audioUrl)
    return songInfo

next_page_token = 'index'
@app.route('/login_page')
def login_page():
    return render_template('login.html')


def render_template_with_session(template, **kwargs):
    if 'loggedin' in session:
        username = session['username']
        return render_template(template, username=username, **kwargs)
    else:
        return render_template(template, username=None, **kwargs)


@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    mycursor = mydb.cursor()
    sql = "SELECT * FROM user WHERE name = %s AND password = %s"
    val = (username, password)
    mycursor.execute(sql, val)
    result = mycursor.fetchone()

    if result:
        session['loggedin'] = True
        session['username'] = username
        return redirect(url_for(next_page_token))
    else:
        flash('Tên đăng nhập hoặc mật khẩu không đúng!', 'error')
        return redirect(url_for('login_page'))

@app.route('/')
def index():
    global next_page_token
    next_page_token = 'index'
    if 'loggedin' in session:
        username = session['username']
        return render_template('index.html', username=username)
    else:
        return render_template('index.html', username=None)
    




@app.route('/signup_page')
def signup_page():
    return render_template_with_session('signup.html')


@app.route('/search', methods=['GET', 'POST'])
def search():

    if request.method == 'POST':
        search_response = youtube.search().list(
            q=request.form['query'],
            part='snippet',
            type='video',
            videoCategoryId='10',  
            maxResults=6
        ).execute()

        songs = []

        for search_result in search_response.get('items', []):
            video_id = search_result['id']['videoId']
            song = getInfoSong(video_id)
            songs.append(song)   
        global next_page_token
        next_page_token = 'index'
        return render_template_with_session('index.html', songs=songs)
    
    



@app.route('/trending', methods=['GET', 'POST'])
def trending():
    

    trending_response = youtube.videos().list(
        part='snippet',
        chart='mostPopular',
        regionCode='VN',
        videoCategoryId='10',
        maxResults=6
    ).execute()

    songs = []

    for trending_result in trending_response.get('items', []):
        video_id = trending_result['id']
        song = getInfoSong(video_id)
        songs.append(song)
    global next_page_token
    next_page_token = 'trending'
    return render_template_with_session('index.html', songs=songs)


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    # Xóa session khi đăng xuất
    session.pop('loggedin', None)
    session.pop('username', None)
    return redirect(url_for('index'))


@app.route('/download', methods=['POST'])
def download():
    if request.method == 'POST':
        songUrl = request.form['songUrl']
        yt = YouTube(songUrl)
        video = yt.streams.filter(only_audio=True).first()

        # Get the path to the Downloads folder
        downloads_path = str(Path.home() / "Downloads")

        # Tạo tên file mới
        file_name = video.default_filename
        base, ext = os.path.splitext(file_name)
        file_name = f"{base}.mp3"  # Thêm đuôi ".mp3" vào tên file

        # Kiểm tra và điều chỉnh tên file nếu cần thiết
        count = 1
        while os.path.exists(os.path.join(downloads_path, file_name)):
            file_name = f"{base}_{count}.mp3"
            count += 1

        outfile = video.download(output_path=downloads_path, filename=file_name)
        return jsonify({'message': 'Downloaded successfully!', 'file_name': file_name})
    
@app.route('/toggle_favorite', methods=['POST'])
def toggle_favorite():
    if 'loggedin' in session:
        username = session['username']
        data = request.json
        song_id = data['songId']
        
        # Kiểm tra xem bài hát đã được lưu trong danh sách yêu thích của người dùng hay chưa
        mycursor = mydb.cursor()
        sql = "SELECT * FROM favorite WHERE name = %s AND id_song = %s"
        val = (username, song_id)
        mycursor.execute(sql, val)
        result = mycursor.fetchone()

        if result:
            # Nếu đã lưu, xóa bài hát khỏi danh sách yêu thích
            delete_sql = "DELETE FROM favorite WHERE name = %s AND id_song = %s"
            delete_val = (username, song_id)
            mycursor.execute(delete_sql, delete_val)
            mydb.commit()
        else:
            # Nếu chưa lưu, thêm bài hát vào danh sách yêu thích
            insert_sql = "INSERT INTO favorite (name, id_song) VALUES (%s, %s)"
            insert_val = (username, song_id)
            mycursor.execute(insert_sql, insert_val)
            mydb.commit()
        return 'OK', 200
    else:
        return 'Unauthorized', 401

@app.route('/check_favorite', methods=['POST'])
def check_favorite():
    if 'loggedin' in session:
        username = session['username']
        data = request.json
        song_id = data['songId']
        
        # Kiểm tra xem bài hát đã được lưu trong danh sách yêu thích của người dùng hay chưa
        mycursor = mydb.cursor()
        sql = "SELECT * FROM favorite WHERE name = %s AND id_song = %s"
        val = (username, song_id)
        mycursor.execute(sql, val)
        result = mycursor.fetchone()

        if result:
            # Nếu đã lưu, trả về kết quả là True
            return jsonify({'isFavorite': True}), 200
        else:
            # Nếu chưa lưu, trả về kết quả là False
            return jsonify({'isFavorite': False}), 200
    else:
        # Trả về mã lỗi 401 nếu người dùng chưa đăng nhập
        return 'Unauthorized', 401

@app.route('/check_login', methods=['GET'])
def check_login():
    if 'loggedin' in session:
        return jsonify({'loggedIn': True}), 200
    else:
        return jsonify({'loggedIn': False}), 401
    
@app.route('/favorite', methods=['GET', 'POST'])
def favorite():
    global next_page_token
    next_page_token= 'favorite'
    if 'loggedin' in session:
        username = session['username']
        mycursor = mydb.cursor()
        sql = "SELECT id_song FROM favorite WHERE name = %s"
        val = (username,)
        mycursor.execute(sql, val)
        result = mycursor.fetchall()
        songs = []

        for row in result:
            song_id = row[0]  # Lấy giá trị của cột id_song từ kết quả truy vấn
            song = getInfoSong(song_id)  # Truyền giá trị của cột id_song vào hàm getInfoSong
            songs.append(song)
        
        

        return render_template_with_session('index.html', songs=songs)
    else:
        return redirect(url_for('login_page'))

@app.route('/signup', methods=['POST'])
def signup():
    username = request.form['username']
    password = request.form['password']
    confirm_password = request.form['confirm-password']
    
    # Kiểm tra độ dài của mật khẩu
    if len(password) < 6:
        flash('Mật khẩu phải chứa ít nhất 6 ký tự!', 'error')
        return redirect(url_for('signup_page'))
    
    # Kiểm tra xem mật khẩu và xác nhận mật khẩu có khớp nhau không
    if password != confirm_password:
        flash('Mật khẩu không khớp!', 'error')
        return redirect(url_for('signup_page'))
    
    # Kiểm tra xem tên người dùng đã tồn tại trong cơ sở dữ liệu chưa
    mycursor = mydb.cursor()
    sql = "SELECT * FROM user WHERE name = %s"
    val = (username,)
    mycursor.execute(sql, val)
    existing_user = mycursor.fetchone()
    if existing_user:
        flash('Tên người dùng đã tồn tại, vui lòng chọn một tên khác!', 'error')
        return redirect(url_for('signup_page'))
    
    # Nếu không có người dùng tồn tại và mật khẩu hợp lệ, thực hiện thêm người dùng mới vào cơ sở dữ liệu
    insert_sql = "INSERT INTO user (name, password) VALUES (%s, %s)"
    insert_val = (username, password)
    mycursor.execute(insert_sql, insert_val)
    mydb.commit()
    
    # Đăng ký thành công, chuyển hướng người dùng đến trang đăng nhập
    flash('Đăng ký thành công! Vui lòng đăng nhập để tiếp tục.', 'success')
    return redirect(url_for('login_page'))


@app.route('/save_played_song', methods=['POST'])
def save_played_song():
    if 'loggedin' not in session:
        return 'Unauthorized', 401

    user = session['username']
    song_id = request.form['songId']

    mycursor = mydb.cursor()

    # Xóa bản ghi cũ nếu đã tồn tại
    delete_sql = "DELETE FROM history WHERE name = %s AND id_song = %s"
    delete_val = (user, song_id)
    mycursor.execute(delete_sql, delete_val)

    # Thêm bản ghi mới
    insert_sql = "INSERT INTO history (name, id_song) VALUES (%s, %s)"
    insert_val = (user, song_id)
    mycursor.execute(insert_sql, insert_val)

    mydb.commit()

    return 'OK', 200
    

@app.route('/history', methods=['GET', 'POST'])
def history():
    global next_page_token
    next_page_token = 'history'
    if 'loggedin' in session:
        username = session['username']
        mycursor = mydb.cursor()
        sql = "SELECT id_song FROM history WHERE name = %s"
        val = (username,)
        mycursor.execute(sql, val)
        result = mycursor.fetchall()
        songs = []

        for row in result:
            song_id = row[0]
            song = getInfoSong(song_id)
            songs.append(song)
        
        
        return render_template_with_session('index.html', songs=songs)
    else:
        return redirect(url_for('login_page'))


@app.route('/delete_history', methods=['POST','GET'])
def delete_history():
    if 'loggedin' in session:
        username = session['username']
        mycursor = mydb.cursor()
        sql = "DELETE FROM history WHERE name = %s"
        val = (username,)
        mycursor.execute(sql, val)
        mydb.commit()
        return redirect(url_for('history'))

if __name__ == '__main__':
    app.run(debug=True)
