#===== Imports ============================================================
import os                     # read the bucket name from the environment
import boto3
from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
    EndpointConnectionError,
)

# ===== Constants =========================================================
FILENAME = "students.txt"
MAX_SCORE = 100
MIN_SCORE = 0
PASSING_GRADE = 60


# ===== AWS S3  ===========================================================
S3_BUCKET = os.environ.get("S3_BUCKET", "your-unique-bucket-name")   # set S3_BUCKET in your shell; placeholder used if unset
S3_KEY = "students.txt"
AWS_REGION = "us-east-1"


# ===== Functions =========================================================

def load_students():
    """Read the notebook on startup and return a list of student dicts."""
    students = []                                           #start with an empty class
    try:
        with open(FILENAME, "r") as file:                   #open for reading
            for line in file:                               #go line by line
                line = line.strip()                         #remove the \n at the end
                if line:                                  # skip blank lines
                    try:
                        name, score = line.split(",", 1)    # maxsplit=1 keeps commas in names safe
                        students.append({
                            "name": name,
                            "score": int(score),            # text -> number
                        })
                    except ValueError:
                        print(f"  Skipping malformed line in {FILENAME}: {line!r}")
    except FileNotFoundError:                             #if file does not yet exist, don't crash
        pass                                              #do nothing
    return students                                       #hand list of student dict. back to caller


def save_students(students):
    """Write the whole class roster back to the notebook (overwrites)."""
    with open(FILENAME, "w") as file:   #open for writing "w", erase old contents
        for student in students:        #loop through every student dict. in list
            file.write(f"{student['name']},{student['score']}\n") #write one name and score per line

# ===== S3 helpers ===========================================================

def upload_to_s3():
    """Upload the local students.txt to the configured S3 bucket."""
    try:
        s3 = boto3.client("s3", region_name=AWS_REGION)
        s3.upload_file(FILENAME, S3_BUCKET, S3_KEY)
        print(f"  Uploaded {FILENAME} to s3://{S3_BUCKET}/{S3_KEY}")
    except FileNotFoundError:
        print(f"  Local file '{FILENAME}' not found. Add and save some students first.")
    except NoCredentialsError:
        print("  No AWS credentials found. Run 'aws configure' in your terminal.")
    except ClientError as e:
        print(f"  S3 error during upload: {e}")


def download_from_s3(students):
    """Download students.txt from S3 and refresh the in-memory list."""
    try:
        s3 = boto3.client("s3", region_name=AWS_REGION)
        s3.download_file(S3_BUCKET, S3_KEY, FILENAME)       # download bucket/key from S3 -> local FILENAME
        print(f"  Downloaded s3://{S3_BUCKET}/{S3_KEY} to {FILENAME}")  # confirm the download


        refreshed = load_students()                         # read the just-downloaded
        students.clear()
        students.extend(refreshed)                          # add every student from the refreshed list
        print(f"  Refreshed roster - {len(students)} student(s) loaded from S3.")
    except NoCredentialsError:                              # no credentials configured
        print("  No AWS credentials found. Run 'aws configure' in your terminal.")
    except EndpointConnectionError:                         # network problem
        print("  Could not connect to AWS. Check your internet connection.")
    except ClientError as e:                                # AWS returned an error - figure out which one
        error_code = e.response.get("Error", {}).get("Code", "")  # dig the error code out of the response dict
        if error_code in ("404", "NoSuchKey"):              # file isn't in the bucket yet
            print(f"  No file at s3://{S3_BUCKET}/{S3_KEY} yet. Upload one first (menu option 4).")
        elif error_code == "NoSuchBucket":                  # bucket name is wrong or bucket was deleted
            print(f"  Bucket '{S3_BUCKET}' does not exist. Set S3_BUCKET in your environment.")
        else:                                               # catch-all for everything else
            print(f"  S3 error during download: {e}")


# ===== Menu actions =========================================================
def add_student(students):
    """Ask the user for one student and append them to the list."""
    while True:
        name = input("Student name: ").strip()              #prompt user to input student name
        if not name:
            print("Name cannot be empty. Please enter a name.")
        elif "," in name:
            print("Name cannot contain a comma. Please re-enter.")
        else:
            break

    # Validate the score -- keep asking until the user gives a number in range.
    while True:                 #start infinite loop
        try:
            score = int(input("Student score: ")) #prompt user to enter score
            if MIN_SCORE <= score <= MAX_SCORE: #check if score is within allowed range
                break                           #if score is valid leave the while loop
            print(f"Score must be between {MIN_SCORE} and {MAX_SCORE}.") #number was in range check failed, tell user
        except ValueError:                      #catches the error int() when input isn't a whole #
            print("Invalid score, please enter a whole number.") #tell user invalid entry, then loop again

    if any(s["name"].lower() == name.lower() for s in students):  #check if student with this name already exists
        print(f"  '{name}' is already in the roster. No duplicate added.") #inform user a duplicate will not be added
        return                   #leave the function

    students.append({"name": name, "score": score}) #add the new student dict to the list
    print(f"  Added {name} ({score}).") #confirm to user that student was added


def view_students(students):
    """Print the class roster with Pass/Fail and the class average."""
    if not students:
        print("\n(No students yet -- add some first!)")
        return

    print("\n=================")
    print("Student Records")
    print("=================\n")

    total = 0          #running total of all scores
    for student in students: #loop over every student dict.
        total += student["score"] #add this student's score to running total
        status = "Pass" if student["score"] >= PASSING_GRADE else "Fail" #decide Pass/Fail
        print(f"{student['name']} - {student['score']}% - {status}") #print one line student name/score/status

    average = total / len(students) #average = total score divided by number of students
    print(f"\nClass Average: {average:.2f}%") #print class average


def delete_student(students):
    """Remove a student from the roster by name."""
    if not students: #can't delete anything from empty list
        print("\n(No students yet -- nothing to delete.)")
        return

    name = input("Enter the name of the student to delete: ").strip()
    for i, student in enumerate(students):
        if student["name"].lower() == name.lower():
            students.pop(i) #remove student at this index from the list
            print(f"  Removed {student['name']} from the roster.")
            return

    print(f"  No student named '{name}' was found.") #if loop finished without finding match, print message


# ===== Main program =========================================================
def main(): #define main entry point
    students = load_students()              # load any existing students from file
    print(f"Loaded {len(students)} student(s) from {FILENAME}.") #tell user how many students were loaded

    while True:
        print("\n--- Menu ---")
        print("1. Add Student")
        print("2. View Students")
        print("3. Delete Student")
        print("4. Upload to S3")
        print("5. Download from S3")
        print("6. Exit")
        choice = input("Choose 1-6: ").strip()

        if choice == "1":
            add_student(students)
        elif choice == "2":
            view_students(students)
        elif choice == "3":
            delete_student(students)
        elif choice == "4":
            save_students(students)
            upload_to_s3()
        elif choice == "5":
            download_from_s3(students)
        elif choice == "6":
            save_students(students)
            print(f"Saved {len(students)} student(s) to {FILENAME}. Goodbye!")
            break
        else:
            print("Please choose 1-6.")


if __name__ == "__main__":
    main()
