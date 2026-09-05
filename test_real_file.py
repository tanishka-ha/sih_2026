from file_converter import convert_to_images

print("Starting conversion...")

result = convert_to_images(
    input_path="sample.pdf",
    output_directory="real_test_output"
)

print("Conversion finished!")
print(result)