from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional, Union
import requests
import uuid
import json
import re
from datetime import datetime, timedelta, date
import calendar # calendar modülü eklendi

app = FastAPI()

# CORS ayarları - Ön yüzün arka uca erişebilmesi için gerekli
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Yapılacaklar listesi öğelerini tutacak basit bir bellek içi depolama
todos_db: List[Dict] = []

# Yapılacaklar listesi öğesi için Pydantic modeli
class TodoItem(BaseModel):
    id: Optional[str] = None
    task: str
    completed: bool = False
    due_date: Optional[str] = None # YYYY-MM-DD formatında tarih stringi

# Yapay zeka sohbet isteği için Pydantic modeli
class ChatRequest(BaseModel):
    message: str
    api_key: str
    current_todos: List[TodoItem]

# Yapılacaklar listesini getiren endpoint
@app.get("/todos", response_model=List[TodoItem])
async def get_todos():
    """Tüm yapılacaklar listesi öğelerini döndürür."""
    return todos_db

# Yeni bir yapılacaklar listesi öğesi ekleyen endpoint
@app.post("/todos", response_model=TodoItem)
async def create_todo(todo: TodoItem):
    """Yeni bir yapılacaklar listesi öğesi ekler."""
    if not todo.id:
        todo.id = str(uuid.uuid4())
    todos_db.append(todo.dict())
    print(f"DEBUG: create_todo - Yeni görev eklendi: {todo.task}, Tarih: {todo.due_date}")
    return todo

# Bir yapılacaklar listesi öğesini güncelleyen endpoint
@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo(item_id: str, todo: TodoItem):
    """Belirtilen ID'ye sahip yapılacaklar listesi öğesini günceller."""
    for idx, existing_todo in enumerate(todos_db):
        if existing_todo["id"] == item_id:
            # Eksik alanları önceki veriden alarak güvenli güncelleme
            updated = {
                "id": item_id,
                "task": todo.task if todo.task is not None else existing_todo["task"],
                "completed": todo.completed if todo.completed is not None else existing_todo["completed"],
                "due_date": todo.due_date if todo.due_date is not None else existing_todo["due_date"]
            }
            todos_db[idx] = updated
            print(f"DEBUG: update_todo - Görev güncellendi: ID={item_id}, Yeni Task='{updated['task']}', Yeni Tarih='{updated['due_date']}', Tamamlandı='{updated['completed']}'")
            return updated
    raise HTTPException(status_code=404, detail="Yapılacaklar öğesi bulunamadı")

# Bir yapılacaklar listesi öğesini silen endpoint
@app.delete("/todos/{item_id}")
async def delete_todo(item_id: str):
    """Belirtilen ID'ye sahip yapılacaklar listesi öğesini siler."""
    found_index = -1
    for idx, todo in enumerate(todos_db):
        if todo["id"] == item_id:
            found_index = idx
            break

    if found_index != -1:
        del todos_db[found_index]
        print(f"DEBUG: delete_todo - Görev silindi: ID={item_id}")
    else:
        print(f"DEBUG: delete_todo - Görev bulunamadı: ID={item_id}")
        raise HTTPException(status_code=404, detail="Yapılacaklar öğesi bulunamadı")
    
    return {"message": "Yapılacaklar öğesi başarıyla silindi"}

# Tarihleri işlemek için yardımcı fonksiyon (yeniden yazıldı ve güçlendirildi)
def parse_relative_date(text: str) -> Optional[str]:
    """
    Kullanıcının metninden göreceli veya kesin tarih ifadelerini ayrıştırır
    ve YYYY-MM-DD formatında döndürür.
    """
    print(f"\nDEBUG: parse_relative_date çağrıldı - Girdi metni: '{text}'")
    if not text:
        print(f"DEBUG: parse_relative_date - Boş metin. None döndürülüyor.")
        return None

    today = date.today()
    print(f"DEBUG: parse_relative_date - Sunucu Bugün: {today} (Haftanın günü: {today.weekday()} - 0=Pzt, 6=Paz)")
    text = text.lower().strip()

    # 1. Kesin tarih formatı YYYY-MM-DD kontrolü
    if re.match(r'^\d{4}-\d{2}-\d{2}$', text):
        try:
            parsed_date = datetime.strptime(text, "%Y-%m-%d").date()
            print(f"DEBUG: parse_relative_date - YYYY-MM-DD formatı eşleşti. Ayrıştırılan tarih: {parsed_date.strftime('%Y-%m-%d')}")
            return text
        except ValueError:
            print(f"DEBUG: parse_relative_date - YYYY-MM-DD formatı ayrıştırma hatası: '{text}'")
            pass # Diğer desenleri denemeye devam et

    # 2. Göreceli tarihler
    if "bugün" in text:
        calculated_date = today.strftime("%Y-%m-%d")
        print(f"DEBUG: parse_relative_date - 'bugün' tespit edildi. Hesaplanan tarih: {calculated_date}")
        return calculated_date
    elif "yarın" in text:
        calculated_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        print(f"DEBUG: parse_relative_date - 'yarın' tespit edildi. Hesaplanan tarih: {calculated_date}")
        return calculated_date
    elif "ertesi gün" in text:
        calculated_date = (today + timedelta(days=2)).strftime("%Y-%m-%d")
        print(f"DEBUG: parse_relative_date - 'ertesi gün' tespit edildi. Hesaplanan tarih: {calculated_date}")
        return calculated_date
    elif "gelecek hafta" in text:
        calculated_date = (today + timedelta(weeks=1)).strftime("%Y-%m-%d")
        print(f"DEBUG: parse_relative_date - 'gelecek hafta' tespit edildi. Hesaplanan tarih: {calculated_date}")
        return calculated_date
    
    # 3. Gün adları (Türkçe karakterleri de dikkate alarak)
    # Python'ın weekday() metodu Pazartesi'yi 0, Pazar'ı 6 olarak döndürür.
    day_names_map = {
        "pazartesi": 0, "salı": 1, "çarşamba": 2, "perşembe": 3, "cuma": 4, "cumartesi": 5, "pazar": 6
    }
    for day_name, weekday_num in day_names_map.items():
        if day_name in text:
            today_weekday = today.weekday()
            target_weekday = weekday_num
            print(f"DEBUG: parse_relative_date - Eşleşen gün adı: '{day_name}'. Hedef hafta günü numarası: {target_weekday}. Mevcut hafta günü: {today_weekday}")

            # Hedef güne ulaşmak için kaç gün gerektiğini hesapla.
            # Eğer hedef gün, bugünün haftasında geçmişse, bir sonraki haftadaki aynı güne git.
            days_until = (target_weekday - today_weekday + 7) % 7
            # Eğer days_until 0 ise ve bugün o gün değilse (yani bugün pazartesiyiz ama "pazartesi" dendiğinde),
            # bir sonraki haftaya geçmek için 7 ekle.
            if days_until == 0 and today_weekday != target_weekday:
                days_until = 7
            
            calculated_date = today + timedelta(days=days_until)
            print(f"DEBUG: parse_relative_date - Hesaplanan days_until: {days_until}. Sonuç tarih: {calculated_date.strftime('%Y-%m-%d')}")
            return calculated_date.strftime("%Y-%m-%d")

    # 4. "15 Temmuz" gibi kesin tarihleri yakalamak için regex
    month_names_map = {
        "ocak": 1, "şubat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "haziran": 6,
        "temmuz": 7, "ağustos": 8, "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12
    }
    # Regex: (gün) (ay_adı) (isteğe bağlı yıl)
    match_date = re.search(r'(\d{1,2})\s*(ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|eylül|ekim|kasım|aralık)(?:\s*(\d{4}))?', text)
    if match_date:
        day = int(match_date.group(1))
        month_name = match_date.group(2)
        month = month_names_map.get(month_name)
        year_str = match_date.group(3)
        
        if month:
            try:
                year = int(year_str) if year_str else today.year
                # Eğer belirtilen ay ve gün, içinde bulunulan yılda daha önce geçmişse, bir sonraki yıla atla (yıl belirtilmemişse)
                if not year_str and (month < today.month or (month == today.month and day < today.day)):
                    year += 1
                
                calculated_date = datetime(year, month, day).strftime("%Y-%m-%d")
                print(f"DEBUG: parse_relative_date - Kesin tarih '{match_date.group(0)}' tespit edildi. Hesaplanan tarih: {calculated_date}")
                return calculated_date
            except ValueError:
                print(f"DEBUG: parse_relative_date - Kesin tarih ayrıştırma hatası: '{match_date.group(0)}'")
                pass
    
    # 5. "29'unda" gibi sayı + 'unda' eklerini yakalama
    match_day_num = re.search(r"(\d{1,2})['’]?(?:ünde|unda|inde|ında)", text)
    if match_day_num:
        try:
            day = int(match_day_num.group(1))
            current_month = today.month
            current_year = today.year

            # Belirtilen günün mevcut ayda geçerli olup olmadığını kontrol et
            # calendar.monthrange(year, month)[1] -> ayın gün sayısını verir
            days_in_current_month = calendar.monthrange(current_year, current_month)[1]
            if not (1 <= day <= days_in_current_month):
                print(f"DEBUG: parse_relative_date - '{day}' mevcut ayda ({current_month}) geçersiz gün. None döndürülüyor.")
                return None # Geçersiz gün numarası

            calculated_date = date(current_year, current_month, day)

            if today.day > day:
                # Eğer belirtilen gün bugünden önceyse, bir sonraki aya geç
                current_month += 1
                if current_month > 12:
                    current_month = 1
                    current_year += 1
                
                # Bir sonraki ayda bu gün geçerli mi kontrol et
                days_in_next_month = calendar.monthrange(current_year, current_month)[1]
                if not (1 <= day <= days_in_next_month):
                    print(f"DEBUG: parse_relative_date - Bir sonraki ayda ({current_month}) '{day}' geçersiz gün. None döndürülüyor.")
                    return None # Bir sonraki ayda bu gün yoksa

                calculated_date = date(current_year, current_month, day)
                print(f"DEBUG: parse_relative_date - '{day}' geçmiş, bir sonraki aya atlandı. Hesaplanan tarih: {calculated_date.strftime('%Y-%m-%d')}")
                return calculated_date.strftime("%Y-%m-%d")

            print(f"DEBUG: parse_relative_date - '{day}' sayısı tespit edildi. Hesaplanan tarih: {calculated_date.strftime('%Y-%m-%d')}")
            return calculated_date.strftime("%Y-%m-%d")

        except ValueError:
            print(f"DEBUG: parse_relative_date - Sayı ayrıştırma hatası veya geçersiz tarih oluşturma: '{match_day_num.group(1)}'")
            pass # Diğer desenleri denemeye devam et

    # 6. "ay sonu" veya "ayın sonunda" gibi ifadeleri yakalama
    if "ay sonu" in text or "ayın sonunda" in text or "ay sonunda" in text:
        last_day_of_month = calendar.monthrange(today.year, today.month)[1]
        calculated_date = date(today.year, today.month, last_day_of_month)
        
        # Eğer "ay sonu" bugünden önce ise (örn. bugün ayın 31'i ise ama ay 30 gün ise), bir sonraki ayın sonuna atla
        if calculated_date < today:
            next_month = today.month + 1
            next_year = today.year
            if next_month > 12:
                next_month = 1
                next_year += 1
            last_day_of_next_month = calendar.monthrange(next_year, next_month)[1]
            calculated_date = date(next_year, next_month, last_day_of_next_month)

        print(f"DEBUG: parse_relative_date - 'ay sonu' tespit edildi. Hesaplanan tarih: {calculated_date.strftime('%Y-%m-%d')}")
        return calculated_date.strftime("%Y-%m-%d")
    
    print(f"DEBUG: parse_relative_date - Hiçbir tarih deseni eşleşmedi. None döndürülüyor.")
    return None


# Yapay zekadan beklediğimiz yapılandırılmış yanıt için ŞEMA
response_schema = {
    "type": "OBJECT",
    "properties": {
        "action": {
            "type": "STRING",
            "enum": ["add", "delete", "update", "none"]
        },
        "added_tasks": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "task_description": {
                        "type": "STRING",
                        "description": "Eklenecek görevin ana açıklaması. Eylem belirten ve tarih ifadelerini bu açıklamadan mutlaka çıkar. Sadece görevin özünü döndür."
                    },
                    "raw_due_date_string": {
                        "type": "STRING",
                        "description": "Kullanıcının mesajında geçen, görevin bitiş tarihini belirten tam ve ham metin (örn: 'yarın', 'cuma günü', '15 Temmuz'). Tarih belirtilmemişse 'null' olarak bırak."
                    }
                },
                "required": ["task_description"]
            },
            "description": "Eğer action 'add' ise eklenecek görevlerin listesi."
        },
        "task_id": {
            "type": "STRING",
            "description": "Silinecek veya güncellenecek görevin ID'si."
        },
        "new_status": {
            "type": "BOOLEAN",
            "description": "Görevin yeni tamamlanma durumu (true/false)."
        },
        "ai_response": {
            "type": "STRING",
            "description": "Yapay zekanın kullanıcıya vereceği konuşma yanıtı."
        }
    },
    "required": ["action", "ai_response"]
}


@app.post("/chat")
async def chat_with_ai(request: ChatRequest):
    """
    Yapay zeka ile sohbet eder ve yapılacaklar listesi üzerinde işlemler yapar.
    Gemini API'sini kullanarak doğal dil girdilerini işler.
    """
    api_key = request.api_key
    user_message = request.message
    current_todos = request.current_todos

    if not api_key:
        raise HTTPException(status_code=400, detail="Gemini API Anahtarı sağlanmadı.")

    # Mevcut yapılacaklar listesini yapay zekaya bağlam olarak gönder
    todos_context = "\n".join([f"{i+1}. {todo.task} (ID: {todo.id}, Tamamlandı: {todo.completed}, Tarih: {todo.due_date if todo.due_date else 'Yok'})" for i, todo in enumerate(current_todos)])
    if not todos_context:
        todos_context = "Şu anda yapılacaklar listesinde hiç öğe yok."

    prompt = f"""
    Sen bir yapılacaklar listesi asistanısın ve uygulamanın adı TaskbuddyAI. Görevleri yönetme konusunda uzmansın ve aynı zamanda sohbet etmeyi de seversin. Kullanıcıyla doğal ve çeşitli bir şekilde iletişim kur.

    Mevcut yapılacaklar listesi:
    {todos_context}

    Kullanıcının mesajı: "{user_message}"

    Lütfen aşağıdaki JSON formatında bir yanıt ver.
    - 'action': 'add' (yeni görev ekle), 'delete' (görev sil), 'update' (görev güncelle), 'none' (hiçbir işlem yapma) olabilir.
    - 'added_tasks': Eğer 'action' 'add' ise, kullanıcının eklemek istediği tüm görevleri ve tarihlerini bu diziye ekle. Her bir görev için 'task_description' ve 'raw_due_date_string' alanlarını doldur. 'task_description' sadece görevin özünü içermeli (örn. "araba yıkama", "parti", "sınav"). Kullanıcının mesajındaki tarih ifadelerini (örn. 'yarın', 'cuma günü', '15 Temmuz') ve 'ekle', 'yapmam gerekiyor', 'listeme ekle', 'todo'ya ekle', 'var', 'için', 'günü', 'gitmem', 'lazım' gibi eylem belirten ifadeleri bu açıklamadan **mutlaka çıkar**.
    - 'raw_due_date_string': Bu alan, kullanıcının mesajında geçen görevin bitiş tarihini belirten **tam ve ham metin** olmalıdır (örn: 'yarın', 'cuma günü', '15 Temmuz'). Eğer tarih belirtilmemişse 'null' olarak bırakılmalıdır. **Kesinlikle YYYY-MM-DD formatında bir tarih döndürme, sadece kullanıcının belirttiği ham metni döndür.**
    - 'task_id': Eğer 'action' 'delete' veya 'update' ise görevin ID'si.
    - 'new_status': Eğer 'action' 'update' ve görev tamamlanma durumu değişiyorsa (true/false).
    - 'ai_response': Kullanıcıya vereceğin konuşma yanıtı. Bu yanıt, sadece görev işlemeli hakkında değil, aynı zamanda genel sohbet sorularına da doğal ve çeşitli bir şekilde cevap vermelidir. Eğer görevle ilgili bir işlem yapmıyorsan, sadece sohbet yanıtı ver. Kendini tanıtırken veya genel sohbet ederken tekrarlayıcı olmaktan kaçın.

    Örnekler:
    Kullanıcı: "Yarın süt almayı ekle."
    Yanıt: {{"action": "add", "added_tasks": [{{"task_description": "Süt al", "raw_due_date_string": "yarın"}}], "ai_response": "Süt alma görevinizi TaskbuddyAI'ye ekledim ve yarın için ayarladım."}}

    Kullanıcı: "15 Temmuz'da doğum günü partisi planlamayı ekle."
    Yanıt: {{"action": "add", "added_tasks": [{{"task_description": "Doğum günü partisi planla", "raw_due_date_string": "15 Temmuz"}}], "ai_response": "Doğum günü partisi planlama görevinizi TaskbuddyAI'ye 15 Temmuz için ekledim."}}

    Kullanıcı: "Cuma günü parti var, bunu todo listeme ekle."
    Yanıt: {{"action": "add", "added_tasks": [{{"task_description": "Parti", "raw_due_date_string": "cuma günü"}}], "ai_response": "Partiyi TaskbuddyAI listenize Cuma günü için ekledim. Şimdiden iyi eğlenceler!"}}

    Kullanıcı: "Bugün spor yapmam gerekiyor."
    Yanıt: {{"action": "add", "added_tasks": [{{"task_description": "Spor yap", "raw_due_date_string": "bugün"}}], "ai_response": "Bugün spor yapma görevinizi TaskbuddyAI'ye ekledim."}}

    Kullanıcı: "Arabamı yarın yıkamam gerekiyor ve 22 Temmuz'da sınavım var."
    Yanıt: {{"action": "add", "added_tasks": [{{"task_description": "Araba yıkama", "raw_due_date_string": "yarın"}}, {{"task_description": "Sınav", "raw_due_date_string": "22 Temmuz"}}], "ai_response": "Araba yıkama ve sınav görevlerinizi TaskbuddyAI'ye ekledim. Arabayı yarın yıkamanız ve 22 Temmuz'daki sınavınız var. Başarılar dilerim!"}}

    Kullanıcı: "İlk görevi tamamlandı olarak işaretle." (ID'yi bulup kullanmalısın)
    Yanıt: {{"action": "update", "task_id": "ilk görevin ID'si", "new_status": true, "ai_response": "İlk görevi TaskbuddyAI'de tamamlandı olarak işaretledim."}}

    Kullanıcı: "3. görevi sil." (ID'yi bulup kullanmalısın)
    Yanıt: {{"action": "delete", "task_id": "3. görevin ID'si", "ai_response": "3. görevi TaskbuddyAI'den sildim."}}

    Kullanıcı: "Merhaba, nasılsın?"
    Yanıt: {{"action": "none", "ai_response": "Merhaba! Ben TaskbuddyAI, gayet iyiyim, teşekkür ederim. Bugün size nasıl yardımcı olabilirim?"}}

    Lütfen sadece JSON yanıtı döndür.
    """

    headers = {
        'Content-Type': 'application/json'
    }
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": response_schema
        }
    }

    try:
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        response = requests.post(gemini_url, headers=headers, json=payload)
        response.raise_for_status()
        gemini_result = response.json()

        if gemini_result and gemini_result.get("candidates"):
            ai_content = gemini_result["candidates"][0]["content"]["parts"][0]["text"]
            print(f"DEBUG: AI'dan gelen ham içerik: {ai_content}")
            ai_data = json.loads(ai_content)
            print(f"DEBUG: AI'dan ayrıştırılan veri: {ai_data}")

            action = ai_data.get("action")
            ai_response_message = ai_data.get("ai_response", "Bir şeyler ters gitti.")
            
            if action == "add":
                added_tasks = ai_data.get("added_tasks")
                if added_tasks and isinstance(added_tasks, list):
                    for task_info in added_tasks:
                        task_description = task_info.get("task_description")
                        raw_due_date_string = task_info.get("raw_due_date_string")
                        due_date = parse_relative_date(raw_due_date_string) if raw_due_date_string else None
                        print(f"DEBUG: Görev ekleniyor: Açıklama='{task_description}', Ham Tarih='{raw_due_date_string}', Ayrıştırılan Tarih='{due_date}'")
                        if task_description:
                            new_todo = TodoItem(task=task_description, due_date=due_date)
                            new_todo.id = str(uuid.uuid4())
                            todos_db.append(new_todo.dict())
                    return {"ai_response": ai_response_message, "todos": todos_db}
                else:
                    # AI'dan tek bir görev dönmesi durumunda (eski yapıya uyumluluk)
                    task_description = ai_data.get("task_description")
                    raw_due_date_string = ai_data.get("raw_due_date_string")
                    due_date = parse_relative_date(raw_due_date_string) if raw_due_date_string else None
                    print(f"DEBUG: Tek görev ekleniyor (geri dönük uyumluluk): Açıklama='{task_description}', Ham Tarih='{raw_due_date_string}', Ayrıştırılan Tarih='{due_date}'")
                    if task_description:
                        new_todo = TodoItem(task=task_description, due_date=due_date)
                        new_todo.id = str(uuid.uuid4())
                        todos_db.append(new_todo.dict())
                        return {"ai_response": ai_response_message, "todos": todos_db}

            elif action == "delete":
                task_id_to_delete = ai_data.get("task_id")
                print(f"DEBUG: Silme eylemi istendi. AI tarafından sağlanan görev ID: {task_id_to_delete}")
                
                # Eğer AI spesifik bir ID sağlamadıysa, mesajdan ID çıkarmaya çalış
                if not task_id_to_delete:
                    if "ilk görevi sil" in user_message.lower() and current_todos:
                        task_id_to_delete = current_todos[0].id
                        print(f"DEBUG: 'ilk görevi sil' tespit edildi. İlk görev ID: {task_id_to_delete} silinmeye çalışılıyor.")
                    elif "son görevi sil" in user_message.lower() and current_todos:
                        task_id_to_delete = current_todos[-1].id
                        print(f"DEBUG: 'son görevi sil' tespit edildi. Son görev ID: {task_id_to_delete} silinmeye çalışılıyor.")
                    elif "görevi sil" in user_message.lower():
                        match = re.search(r'(\d+)\.\s*görevi sil', user_message.lower())
                        if match and current_todos:
                            task_index = int(match.group(1)) - 1
                            if 0 <= task_index < len(current_todos):
                                task_id_to_delete = current_todos[task_index].id
                                print(f"DEBUG: '{task_index + 1}. görevi sil' tespit edildi. Görev {task_index + 1} ID: {task_id_to_delete} silinmeye çalışılıyor.")
                
                if task_id_to_delete:
                    found_index = -1
                    for idx, todo in enumerate(todos_db):
                        if todo["id"] == task_id_to_delete:
                            found_index = idx
                            break
                    if found_index != -1:
                        del todos_db[found_index]
                        print(f"DEBUG: ID {task_id_to_delete} olan görev silindi.")
                        return {"ai_response": ai_response_message, "todos": todos_db}
                    else:
                        print(f"DEBUG: ID {task_id_to_delete} olan görev todos_db'de bulunamadı.")
                        return {"ai_response": ai_response_message + " (Silinecek görev bulunamadı.)", "todos": todos_db}
                else:
                    print(f"DEBUG: Silme eylemi: Mesajdan veya AI yanıtından görev ID belirlenemedi.")
                    return {"ai_response": ai_response_message + " (Silinecek görevin ID'si belirlenemedi.)", "todos": todos_db}

            elif action == "update":
                task_id_to_update = ai_data.get("task_id")
                new_status = ai_data.get("new_status")
                ai_provided_task_description = ai_data.get("task_description") # AI'dan gelen yeni görev açıklaması
                ai_provided_raw_due_date = ai_data.get("raw_due_date_string")
                new_due_date = parse_relative_date(ai_provided_raw_due_date) if ai_provided_raw_due_date else None
                
                print(f"DEBUG: Güncelleme eylemi istendi. AI tarafından sağlanan görev ID: {task_id_to_update}, yeni durum: {new_status}, ham tarih: {ai_provided_raw_due_date}, ayrıştırılan yeni tarih: {new_due_date}, yeni açıklama: {ai_provided_task_description}")
                
                # Eğer AI spesifik bir ID sağlamadıysa, mesajdan ID çıkarmaya çalış
                if not task_id_to_update:
                    if ("ilk görevi tamamla" in user_message.lower() or "ilk görevi tamamlandı" in user_message.lower()) and current_todos:
                        task_id_to_update = current_todos[0].id
                        print(f"DEBUG: 'ilk görevi tamamla' tespit edildi. İlk görev ID: {task_id_to_update} tamamlanmaya çalışılıyor.")
                    elif ("son görevi tamamla" in user_message.lower() or "son görevi tamamlandı" in user_message.lower()) and current_todos:
                        task_id_to_update = current_todos[-1].id
                        print(f"DEBUG: 'son görevi tamamla' tespit edildi. Son görev ID: {task_id_to_update} tamamlanmaya çalışılıyor.")
                    elif "görevi tamamla" in user_message.lower() or "görevi tamamlandı" in user_message.lower():
                        match = re.search(r'(\d+)\.\s*görevi tamamla', user_message.lower())
                        if match and current_todos:
                            task_index = int(match.group(1)) - 1
                            if 0 <= task_index < len(current_todos):
                                task_id_to_update = current_todos[task_index].id
                                print(f"DEBUG: '{task_index + 1}. görevi tamamla' tespit edildi. Görev {task_index + 1} ID: {task_id_to_update} tamamlanmaya çalışılıyor.")
                    elif "görevi düzenle" in user_message.lower() or "görevi güncelle" in user_message.lower():
                         # Burada görev açıklaması içeren bir güncelleme varsa, AI'dan gelen task_id'si yoksa
                         # bu kısımdan ID çıkarımı yapmak zor, çünkü kullanıcı "X görevini Y olarak güncelle" diyebilir.
                         # Bu durumda AI'ın task_id dönmesi esastır.
                        print(f"DEBUG: Güncelleme eylemi: 'görevi düzenle/güncelle' tespit edildi, ancak AI veya mesaj tarafından belirli bir görev ID sağlanmadı.")
                        return {"ai_response": ai_response_message + " (Güncellenecek görevin ID'si belirlenemedi.)", "todos": todos_db}

                if task_id_to_update:
                    for idx, existing_todo in enumerate(todos_db):
                        if existing_todo["id"] == task_id_to_update:
                            if new_status is not None:
                                todos_db[idx]["completed"] = new_status
                                print(f"DEBUG: Görev {task_id_to_update} tamamlanma durumu {new_status} olarak güncellendi.")
                            if ai_provided_task_description: # AI yeni görev açıklaması sağladıysa
                                todos_db[idx]["task"] = ai_provided_task_description
                                print(f"DEBUG: Görev {task_id_to_update} açıklaması '{ai_provided_task_description}' olarak güncellendi.")
                            if new_due_date is not None:
                                todos_db[idx]["due_date"] = new_due_date
                                print(f"DEBUG: Görev {task_id_to_update} tarihi '{new_due_date}' olarak güncellendi.")
                            return {"ai_response": ai_response_message, "todos": todos_db}
                    print(f"DEBUG: Güncelleme eylemi: ID {task_id_to_update} olan görev todos_db'de bulunamadı.")
                    return {"ai_response": ai_response_message + " (Güncellenecek görev bulunamadı.)", "todos": todos_db}
                else:
                    print(f"DEBUG: Güncelleme eylemi: Mesajdan veya AI yanıtından görev ID belirlenemedi.")
                    return {"ai_response": ai_response_message + " (Güncellenecek görevin ID'si belirlenemedi.)", "todos": todos_db}

            elif action == "none":
                print(f"DEBUG: AI tarafından hiçbir eylem istenmedi. Yanıt: {ai_response_message}")
                return {"ai_response": ai_response_message, "todos": todos_db}
            else:
                print(f"DEBUG: AI yanıt eylemi '{action}' tanınmıyor.")
                return {"ai_response": "Yapay zeka yanıtı anlaşılamadı.", "todos": todos_db}
        else:
            print(f"DEBUG: Gemini sonucu boş veya geçersiz: {gemini_result}")
            return {"ai_response": "Yapay zeka yanıtı boş veya geçersiz.", "todos": todos_db}

    except requests.exceptions.RequestException as e:
        print(f"Gemini API isteği hatası: {e}")
        raise HTTPException(status_code=500, detail=f"Gemini API hatası: {e}")
    except json.JSONDecodeError as e:
        print(f"Gemini API yanıtı JSON ayrıştırma hatası: {e}")
        raise HTTPException(status_code=500, detail=f"Yapay zeka yanıtı işlenirken hata oluştu: {e}")
    except Exception as e:
        print(f"Bilinmeyen bir hata oluştu: {e}")
        raise HTTPException(status_code=500, detail=f"Sunucu hatası: {e}")