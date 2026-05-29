# Student Grade Tracker

A Python command-line application that manages student grade records locally and synchronizes them with Amazon S3 for cloud backup and cross-device access.

---

## 1. Project Overview

This project is a Python-based **Student Grade Tracker** that lets a teacher add, view, and delete student records, persist them in a local text file, and synchronize that file with an Amazon S3 bucket. The local file is the primary source of truth during a session, and S3 acts as a remote backup that can be pushed to or refreshed from at any time.

The program demonstrates core programming concepts including lists, dictionaries, file input/output, exception handling, input validation, and cloud integration with AWS via the boto3 SDK.

---

## 2. Features

- Add new student records with input validation (no empty names, no commas in names, scores must be whole numbers between 0 and 100)
- View all student records with automatic Pass/Fail status and class average
- Delete a student by name (case-insensitive match)
- Save records to a local text file (`students.txt`) automatically on exit
- Upload the local file to an Amazon S3 bucket on demand
- Download the file from S3 to refresh the local roster
- Graceful handling of common error conditions: missing file, missing credentials, network failure, missing bucket, missing object
- Skip malformed lines on load rather than crash on a single bad row

---

## 3. Technologies Used

- **Python 3** — core programming language
- **boto3** — Amazon's AWS SDK for Python
- **botocore.exceptions** — typed AWS error handling (`ClientError`, `NoCredentialsError`, `EndpointConnectionError`)
- **Amazon S3** — cloud object storage
- **AWS CLI** — local credential configuration via `aws configure`
- **Plain text file (CSV-style)** — local persistence layer

---

## 4. How to Run the Program

### Prerequisites

You'll need Python 3 installed, an AWS account with an IAM user that has S3 access, and an existing S3 bucket.

### Steps

1. **Install Python 3** from [python.org](https://www.python.org/downloads/) or via Homebrew (`brew install python3` on macOS).

2. **Install boto3**:
   ```bash
   python3 -m pip install boto3
   ```

3. **Configure AWS credentials**:
   ```bash
   aws configure
   ```
   You'll be prompted for your Access Key ID, Secret Access Key, default region, and output format. This writes credentials to `~/.aws/credentials` — boto3 reads from there automatically. Verify with:
   ```bash
   aws sts get-caller-identity
   ```

4. **Customize the configuration constants** at the top of `student_records.py`. These are placeholders and **must** be replaced with your own values before running:
   ```python
   S3_BUCKET = "your-unique-bucket-name"   # the name of the S3 bucket you created
   S3_KEY    = "students.txt"              # the object name inside the bucket
   AWS_REGION = "us-east-1"                # the region your bucket lives in
   ```
   Bucket names must be globally unique across all of AWS, so pick something specific to you (for example, `myinitials-grade-tracker-2026`).

5. **Run the program**:
   ```bash
   python3 student_records.py
   ```

### Security note

This project intentionally keeps **no AWS credentials in the source code**. boto3 reads them from `~/.aws/credentials`, which lives outside the repository. Before publishing this code anywhere public, double-check that you have not pasted access keys into any constant, and confirm `~/.aws/credentials` is excluded from version control (it lives outside the project folder by default).

---

## 5. Code Walkthrough

The program is organized into five logical sections: **Imports**, **Constants**, **AWS S3 settings**, **Functions**, and **Main program**.

### Storing students as a list of dictionaries

Each student is a dictionary with `name` and `score` keys. All students live in a single list called `students`, which is loaded once at startup and modified in memory throughout the session.

```python
students.append({
    "name": name,
    "score": int(score),
})
```

This pattern is flexible — adding a future field like `email` or `grade_level` is a one-line edit, with no schema migration needed.

### Reading from disk safely

`load_students()` opens the local file, splits each line on its first comma, converts the score to an integer, and returns a list of dictionaries. A `FileNotFoundError` is intentionally swallowed — on the very first run there's no file yet, and that's a normal state, not an error.

```python
try:
    name, score = line.split(",", 1)   # maxsplit=1 keeps commas in names safe
    students.append({"name": name, "score": int(score)})
except ValueError:
    print(f"  Skipping malformed line in {FILENAME}: {line!r}")
```

The inner `try/except ValueError` skips any line that doesn't parse cleanly, so one bad row doesn't kill the whole load.

### Validating new student input

`add_student()` runs two separate validation loops — one for the name and one for the score. Each loop keeps re-prompting until the user provides valid input.

```python
while True:
    try:
        score = int(input("Student score: "))
        if MIN_SCORE <= score <= MAX_SCORE:
            break
        print(f"Score must be between {MIN_SCORE} and {MAX_SCORE}.")
    except ValueError:
        print("Invalid score, please enter a whole number.")
```

The chained comparison `MIN_SCORE <= score <= MAX_SCORE` is the Pythonic way to express a range check — more readable than `score >= 0 and score <= 100`.

### Uploading to S3

`upload_to_s3()` creates a boto3 client (which automatically picks up credentials from `~/.aws/credentials`) and pushes the local file to the configured bucket and key.

```python
s3 = boto3.client("s3", region_name=AWS_REGION)
s3.upload_file(FILENAME, S3_BUCKET, S3_KEY)
```

The whole block is wrapped in specific exception handlers — `FileNotFoundError`, `NoCredentialsError`, and the generic `ClientError` — so the user gets a meaningful message rather than a stack trace.

### Refreshing in-memory state after a download

`download_from_s3()` is the most interesting function. After pulling the file from S3, it has to refresh the in-memory roster *without breaking the reference held by `main()`*. It does this by mutating the list in place:

```python
refreshed = load_students()
students.clear()             # empty the existing list IN PLACE
students.extend(refreshed)   # add every student from the refreshed list
```

Using `students = refreshed` would only rebind the local name inside the function — the original list in `main()` would still hold the old data. Mutating the same list object keeps every reference in sync.

### The menu loop

The `main()` function is a classic REPL pattern: load data, then loop showing a menu, dispatch to the right handler, and exit when the user picks option 6.

```python
while True:
    print("\n--- Menu ---")
    print("1. Add Student")
    ...
    choice = input("Choose 1-6: ").strip()
    if choice == "1":
        add_student(students)
    elif choice == "4":
        save_students(students)   # save locally first
        upload_to_s3()            # then upload that file to S3
```

Option 4 (Upload to S3) calls `save_students()` *before* `upload_to_s3()` because the upload reads from disk — syncing the in-memory state to disk first guarantees what we upload is current.

---

## 6. Sample Program Output

```
Loaded 2 student(s) from students.txt.

--- Menu ---
1. Add Student
2. View Students
3. Delete Student
4. Upload to S3
5. Download from S3
6. Exit
Choose 1-6: 2

=================
Student Records
=================

Tim - 76% - Pass
Leo - 95% - Pass

Class Average: 85.50%

--- Menu ---
1. Add Student
2. View Students
3. Delete Student
4. Upload to S3
5. Download from S3
6. Exit
Choose 1-6: 4
  Uploaded students.txt to s3://your-unique-bucket-name/students.txt

--- Menu ---
1. Add Student
2. View Students
3. Delete Student
4. Upload to S3
5. Download from S3
6. Exit
Choose 1-6: 6
Saved 2 student(s) to students.txt. Goodbye!
```

---

## 7. Example Data File

The local file `students.txt` is plain text in `name,score` format, one student per line:

```
Tim,76
Leo,95
```

This format is human-readable, easy to debug, and compatible with any spreadsheet program. The same format is uploaded to and downloaded from S3 with no transformation.

---

## 8. Challenges I Faced

**The IAM username vs Access Key ID confusion.**

My biggest challenge wasn't the Python code but getting AWS set up. When I ran `aws configure`, I typed my IAM username into the Access Key ID field, not realizing the Access Key ID is a completely separate value that starts with `AKIA...`. I figured out my mistake when `aws s3 ls` failed with this error:

```
An error occurred (InvalidAccessKeyId) when calling the ListBuckets operation:
The AWS Access Key Id you provided does not exist in our records.
Additional error details:
AWSAccessKeyId: myusername
```

That last line was the giveaway — AWS printed the value I had given it right back at me, and I recognized it as my username rather than an actual access key (a real Access Key ID always starts with `AKIA` and is exactly 20 characters long, so the shape didn't match).

I fixed it by generating a new access key in the IAM console under **Security credentials → Create access key → CLI option**, copying both the key and the secret immediately (since the secret is only shown once), and re-running `aws configure` with the real values — this time actually pasting the new key instead of pressing Enter past the existing default.

I verified the fix by running `aws sts get-caller-identity` and seeing my correct ARN come back. After that, the Python script could upload to and download from S3 with no errors.

---

## 9. What I Learned

Through this project, I learned how to:

- **Combine lists and dictionaries** as a flexible in-memory data structure — each student is a dictionary, and a list of dictionaries cleanly represents a collection of records with multiple fields.
- **Read and write files in Python** using context managers (`with open(...) as f`), which guarantee the file is closed automatically even if something goes wrong.
- **Validate user input** with `try/except` blocks and explicit range checks — handling both bad types (a non-numeric score) and bad values (a score outside 0–100) before they propagate further.
- **Use specific exception handling** rather than catching everything with a bare `except:` — different errors mean different things to the user, and treating them separately leads to clearer error messages.
- **Configure and use the AWS SDK** via boto3, including understanding boto3's credential lookup chain (environment variables → config file → IAM role) and why that order matters.
- **Upload and download files from Amazon S3** using `s3.upload_file()` and `s3.download_file()`, and how to interpret error codes (`NoSuchKey`, `NoSuchBucket`) from a `ClientError`.
- **Refresh in-memory state cleanly** by mutating a list in place with `clear()` and `extend()` rather than reassigning, so other references to the same list see the update.
- **Build a menu-driven CLI application** with a clear separation between presentation (the menu loop) and underlying actions (each function).
- **Diagnose AWS credential issues** using `aws sts get-caller-identity` and direct inspection of `~/.aws/credentials`.

---

## 10. Future Improvements

- **Store data in JSON format** instead of plain text. Python's built-in `json` module handles encoding edge cases (commas in names, special characters) that the current CSV format can break on.
- **Move the bucket name to an environment variable** so the same script works for multiple users without code edits: `S3_BUCKET = os.environ.get("S3_BUCKET", "default-name")`.
- **Enable S3 versioning** on the bucket so every upload preserves the previous version, allowing rollback if a bad save corrupts the file.
- **Add timestamped backup keys** like `students-2026-05-28T14-32-01.txt` alongside the canonical `students.txt`, giving a manual history without relying on bucket versioning.
- **Add a search feature** so the user can find a student by partial name match rather than scrolling the full roster.
- **Add a sort option** for viewing students by score (ascending or descending) or alphabetically.
- **Build a small web frontend** using Flask or FastAPI so the same logic is usable in a browser, with S3 as the shared data store across multiple clients.
- **Add unit tests** with `pytest` covering the file I/O, validation logic, and S3 client (mocked with `moto`).

---

## Author

**Your Name** — built as a final project for an AWS + Python lab.
