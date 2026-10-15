# AI-based CV Scoring

Công cụ dòng lệnh viết bằng Python, sử dụng Gemini API để trích xuất thông tin từ CV PDF và đánh giá ứng viên theo mô tả công việc (JD). Kết quả gồm điểm theo từng nhóm, bằng chứng trích từ CV, mức độ đáp ứng yêu cầu và gợi ý cải thiện.

Dự án được phát triển từ bản tutorial Việt hóa dựa trên [interviewstreet/hiring-agent](https://github.com/interviewstreet/hiring-agent).

## Tính năng

- Đọc PDF thành Markdown và giữ lại các liên kết trong tài liệu.
- Trích xuất thông tin cá nhân, kinh nghiệm, học vấn, kỹ năng, dự án và giải thưởng theo schema Pydantic.
- Phân tích JD và áp dụng rubric theo cấp độ ứng viên.
- Đánh giá kèm trích dẫn, điểm mạnh, khoảng trống kỹ năng, câu hỏi phỏng vấn và gợi ý sửa CV.
- Tính tổng điểm trên thang 100 bằng Python, kiểm tra trích dẫn và áp dụng giới hạn điểm theo dữ liệu CV.
- Cache kết quả trích xuất, hỗ trợ chấm nhiều lần và xuất báo cáo JSON.
- Ghi nhận model thực tế được sử dụng; hỗ trợ retry và model dự phòng khi được bật.

## Luồng xử lý

```text
CV PDF → Văn bản → Trích xuất thông tin → Đánh giá → Báo cáo terminal / JSON
                                              ↑
                              JD (.txt) → Phân tích yêu cầu
```

Toàn bộ CV được trích xuất bằng một lời gọi Gemini khi chưa có cache. Nếu cung cấp JD, chương trình gọi Gemini để phân tích JD trước khi chấm điểm. Số lời gọi thực tế còn phụ thuộc vào số lần chấm, retry và việc kiểm tra lại trích dẫn.

## Yêu cầu

- Python 3.10 trở lên, có `pip` và `venv`.
- Git nếu tải mã nguồn bằng `git clone`.
- Gemini API key, tạo tại [Google AI Studio](https://aistudio.google.com/apikey).
- Kết nối Internet khi cài thư viện và gọi Gemini API.

Chạy các lệnh dưới đây tại thư mục gốc dự án, nơi chứa `main.py` và `requirements.txt`.

## Cài đặt

Tải repository bằng **Code → Download ZIP** trên GitHub rồi giải nén, hoặc clone bằng URL của repository. Thay các giá trị trong dấu `<...>` bằng thông tin thực tế:

```text
git clone <repository-url>
cd <repository-directory>
```

### Linux (Bash)

```bash
# Tạo và kích hoạt môi trường ảo
python3 -m venv .venv
source .venv/bin/activate

# Cài thư viện
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Tạo cấu hình cho lần cài đặt đầu tiên
cp .env.example .env
```

Mở `.env` bằng trình soạn thảo và điền `GEMINI_API_KEY` theo phần cấu hình bên dưới. Chỉ sao chép file mẫu khi chưa có `.env` để tránh ghi đè cấu hình đang dùng.

### Windows (PowerShell)

```powershell
# Tạo và kích hoạt môi trường ảo
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# Cài thư viện
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Tạo cấu hình cho lần cài đặt đầu tiên và mở để chỉnh sửa
Copy-Item .env.example .env
notepad .env
```

Nếu máy không có lệnh `py`, dùng `python -m venv .venv` sau khi kiểm tra `python --version` trả về Python 3.10 trở lên. Chỉ sao chép file mẫu khi chưa có `.env`.

Nếu PowerShell chặn `Activate.ps1`, cho phép chạy script trong **phiên PowerShell hiện tại**, rồi kích hoạt lại:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Bạn cũng có thể gọi trực tiếp Python trong môi trường ảo mà không kích hoạt:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py .\sample\sample_resume.pdf
```

## Cấu hình

Cấu hình tối thiểu trong `.env`:

```dotenv
GEMINI_API_KEY=your_gemini_api_key
MODEL=gemini-flash-latest
```

`MODEL` ở trên là giá trị mặc định trong mã nguồn. Chọn model mà tài khoản API của bạn có quyền truy cập. Hạn mức và chi phí phụ thuộc vào model, tài khoản và chính sách của nhà cung cấp.

| Biến môi trường | Ý nghĩa | Mặc định trong `config.py` |
| --- | --- | --- |
| `GEMINI_API_KEY` | API key dùng để gọi Gemini | Trống, cần điền để chấm CV |
| `MODEL` | Model chính | `gemini-flash-latest` |
| `MODEL_FALLBACKS` | Các model dự phòng, phân cách bằng dấu phẩy | `gemini-flash-lite-latest` |
| `ALLOW_FALLBACK` | Bật fallback khi gọi các hàm Python trực tiếp | `false` |
| `MAX_RETRIES` | Số lượt thử tối đa cho mỗi model, gồm lượt đầu | `3` |
| `RETRY_BASE_SECONDS` | Thời gian chờ cơ sở khi retry lỗi 503, tính bằng giây | `2` |
| `RATE_LIMIT_WAIT_SECONDS` | Thời gian chờ cơ sở khi lỗi 429 không cung cấp thời gian retry | `60` |

File `.env.example` có thể đặt giá trị khác mặc định trong code. Khi chạy qua `main.py`, fallback chỉ bật bằng `--allow-fallback`, kể cả khi `.env` có `ALLOW_FALLBACK=true`; `--no-fallback` được ưu tiên nếu truyền cả hai cờ.

## Chạy chương trình

Mỗi lần mở terminal mới, hãy chuyển vào thư mục dự án và kích hoạt lại môi trường ảo.

### Linux (Bash)

```bash
source .venv/bin/activate

# Chạy với CV mẫu có sẵn
python main.py sample/sample_resume.pdf

# Chấm CV của bạn
python main.py "/home/user/Documents/My CV.pdf"

# Chấm theo JD và xuất JSON; chuẩn bị file JD UTF-8 trước khi chạy
python main.py "/home/user/Documents/My CV.pdf" "/home/user/Documents/backend-jd.txt" --json report.json
```

### Windows (PowerShell)

```powershell
.\.venv\Scripts\Activate.ps1

# Chạy với CV mẫu có sẵn
python main.py .\sample\sample_resume.pdf

# Chấm CV của bạn
python main.py "C:\Users\YourName\Documents\My CV.pdf"

# Chấm theo JD và xuất JSON; chuẩn bị file JD UTF-8 trước khi chạy
python main.py "C:\Users\YourName\Documents\My CV.pdf" "C:\Users\YourName\Documents\backend-jd.txt" --json report.json
```

Thay các đường dẫn ví dụ bằng file thực tế; đặt đường dẫn có khoảng trắng trong dấu ngoặc kép. CV mẫu nằm tại [`sample/sample_resume.pdf`](sample/sample_resume.pdf). Nếu không truyền JD, chương trình dùng cấp độ **Fresher** mặc định.

Báo cáo JSON được ghi theo đường dẫn sau `--json`; nếu dùng `report.json`, file sẽ nằm trong thư mục terminal hiện tại. Thư mục cha của file đầu ra phải tồn tại.

### Tùy chọn dòng lệnh

Các lệnh sau dùng được trên cả Bash và PowerShell sau khi kích hoạt môi trường ảo:

```text
python main.py --help
python main.py sample/sample_resume.pdf --json report.json
python main.py sample/sample_resume.pdf --no-cache --runs 3
python main.py sample/sample_resume.pdf --model gemini-flash-latest --no-fallback
python main.py sample/sample_resume.pdf --allow-fallback --fallback-model gemini-flash-lite-latest
```

| Tham số | Chức năng |
| --- | --- |
| `pdf` | Đường dẫn CV PDF, bắt buộc |
| `jd` | Đường dẫn JD dạng văn bản UTF-8, tùy chọn, đứng sau `pdf` |
| `--json PATH` | Xuất báo cáo JSON |
| `--no-cache` | Bỏ qua cả đọc và ghi cache trích xuất |
| `--runs N` | Chấm `N` lần rồi tổng hợp điểm theo trung vị; dùng số nguyên từ 1 trở lên |
| `--model NAME` | Chọn model chính cho lần chạy |
| `--allow-fallback` | Cho phép dùng model dự phòng |
| `--fallback-model NAME` | Chỉ định model dự phòng; dùng cùng `--allow-fallback` |
| `--no-fallback` | Tắt fallback |

Cache trích xuất lưu tại `.cache/`, dựa trên hash của văn bản đọc từ PDF. Cache không bao gồm JD hoặc kết quả chấm điểm. Khi đổi model hay prompt trích xuất, dùng `--no-cache` để lấy kết quả mới. Tăng `--runs` sẽ tăng số lời gọi API và không đảm bảo điểm giống nhau giữa các lần chạy.

Sau khi dùng xong, thoát môi trường ảo bằng `deactivate` trên cả hai hệ điều hành.

## Kết quả đầu ra

Báo cáo hiển thị điểm từng nhóm, trích dẫn và mức độ tin cậy; tổng điểm `/100` và mức xếp loại; mức độ đáp ứng yêu cầu JD; điểm mạnh, rủi ro, câu hỏi phỏng vấn và gợi ý cải thiện CV. Phần độ tin cậy ghi nhận các model đã gọi và cảnh báo phát hiện được.

Xem [`expected-output.txt`](expected-output.txt) để tham khảo định dạng đầu ra. Đây là kết quả minh họa, không phải kết quả cố định cho mọi lần chạy.

## Kiểm thử

Sau khi cài thư viện và kích hoạt môi trường ảo, chạy trên Bash hoặc PowerShell:

```text
python -m pytest -q
```

Các bài kiểm thử hiện tại kiểm tra logic tính điểm, kiểm chứng dữ liệu và cache bằng dữ liệu giả lập; không gọi Gemini API và không cần API key.

## Cấu trúc dự án

```text
.
├── main.py                  # CLI, cache và xuất báo cáo
├── config.py                # Đọc cấu hình môi trường
├── llm.py                   # Gemini client, structured output, retry và fallback
├── extract.py               # Đọc PDF và trích xuất CV
├── evaluate.py              # Phân tích JD và đánh giá CV
├── scoring.py               # Tính điểm, kiểm tra bằng chứng và giới hạn điểm
├── models.py                # Schema Pydantic và rubric
├── prompts/
│   ├── template_manager.py  # Nạp và render template
│   └── templates/           # Prompt Jinja
├── sample/
│   └── sample_resume.pdf    # CV mẫu
├── scripts/                 # Script hỗ trợ chạy thử
├── tests/                   # Kiểm thử và fixtures
├── .env.example             # Cấu hình mẫu
├── .gitignore
├── requirements.txt
└── expected-output.txt      # Đầu ra minh họa
```

Để thay đổi cách đánh giá, xem prompt trong [`prompts/templates/`](prompts/templates/), rubric trong [`models.py`](models.py) và logic tính điểm trong [`scoring.py`](scoring.py). Khi sửa rubric, cần cập nhật đồng bộ prompt, schema và logic liên quan.

## Xử lý lỗi thường gặp

| Hiện tượng | Cách xử lý |
| --- | --- |
| Linux báo thiếu `venv` hoặc `ensurepip` | Cài gói hỗ trợ `venv` tương ứng với Python qua trình quản lý gói của hệ điều hành, rồi tạo lại môi trường ảo |
| `python` / `py` không được nhận diện | Kiểm tra cài đặt Python và PATH, mở terminal mới rồi kiểm tra phiên bản |
| `ModuleNotFoundError` | Kích hoạt đúng `.venv`, rồi chạy `python -m pip install -r requirements.txt` |
| Chưa có `GEMINI_API_KEY` | Kiểm tra `.env` ở thư mục gốc, tên biến và giá trị API key |
| API báo lỗi xác thực hoặc model không truy cập được | Kiểm tra API key, quyền truy cập và tên `MODEL` trong cấu hình |
| API trả lỗi 429 hoặc 503 | Chương trình có retry; nếu hết hạn mức, kiểm tra quota tài khoản hoặc thử lại sau; chỉ bật fallback khi có model dự phòng khả dụng |
| Không tìm thấy CV hoặc JD | Kiểm tra đường dẫn và thư mục terminal hiện tại; đặt đường dẫn có khoảng trắng trong dấu ngoặc kép |
| JD lỗi mã hóa | Lưu file JD dạng văn bản UTF-8 |
| CV trích xuất thiếu nội dung | Ưu tiên PDF có lớp văn bản; dự án chưa có bước OCR riêng cho PDF scan |

## Dữ liệu và giới hạn

Nội dung CV và JD được gửi đến Gemini API để xử lý. Cache `.cache/` lưu thông tin CV đã trích xuất trên máy; báo cáo JSON có thể chứa dữ liệu cá nhân. Chỉ dùng tài liệu mà bạn có quyền xử lý và kiểm tra các file trước khi đưa lên GitHub. `.env`, `.venv/` và `.cache/` đã được khai báo trong `.gitignore`; các báo cáo tự đặt tên như `report.json` chưa được bỏ qua mặc định.

Điểm số phản ánh nội dung được nêu trong CV và JD, có thể thay đổi theo model và từng lần chạy. Liên kết GitHub, kinh nghiệm và số liệu tự công bố chưa được xác minh qua nguồn bên ngoài. Kết quả phục vụ tham khảo và cần con người xem xét khi sử dụng trong tuyển dụng.

## Đóng góp và ghi nhận

Có thể đóng góp qua issue hoặc pull request với mô tả vấn đề, thay đổi đề xuất và cách kiểm tra. Khi thay đổi logic, chạy bộ kiểm thử và cập nhật tài liệu liên quan; dùng dữ liệu giả lập thay cho CV thật trong ví dụ và fixtures.

Cảm ơn dự án [interviewstreet/hiring-agent](https://github.com/interviewstreet/hiring-agent) và bản tutorial HuyG AI đã cung cấp nền tảng ban đầu. Repository hiện chưa có file `LICENSE` riêng; cần xác định giấy phép và giữ các thông báo bản quyền áp dụng khi phân phối mã nguồn.
# AI-based-CV-scoring
