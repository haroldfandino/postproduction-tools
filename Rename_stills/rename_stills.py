import os
import re

def rename_images():
    """Renames image files in the current directory sequentially based on user input."""

    folder_path = os.getcwd()  # Get the current working directory

    image_files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]  # Add more extensions if needed

    if not image_files:
        print("Error: No PNG, JPG or JPEG images found in the current directory.")
        return

    image_files.sort() # Sort files alphabetically to ensure consistent numbering

    project_name = input("Enter the project name: ")
    project_type = input("Enter the project type: ")


    for i, filename in enumerate(image_files):
        # Construct new filename
        new_filename = f"{project_name}_{project_type}_Still_{i+1:02d}.png"  # :02d formats the number with leading zeros (e.g., 01, 02)

        old_filepath = os.path.join(folder_path, filename)
        new_filepath = os.path.join(folder_path, new_filename)

        try:
            os.rename(old_filepath, new_filepath)
            print(f"Renamed '{filename}' to '{new_filename}'")
        except OSError as e:
            print(f"Error renaming '{filename}': {e}")


if __name__ == "__main__":
    rename_images()
