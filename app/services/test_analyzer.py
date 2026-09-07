from app.services.analyzer import analyze_repository


result = analyze_repository("test_repo")


print("\n========== STATIC ANALYSIS RESULT ==========\n")

print("Files analyzed:", result["files_analyzed"])
print("Total code lines:", result["total_code_lines"])
print("Total functions:", result["total_functions"])
print("Total classes:", result["total_classes"])

print("\nPotential secrets:")
print(result["potential_secrets"])

print("\nTests:")
print(result["tests"])

print("\nStatic Analysis Score:")
print(result["static_score"])

print("\nFile details:")

for file in result["files"]:

    print("\n-------------------------")

    print("File:", file["file"])
    print("AST:", file["ast"])
    print("LOC:", file["loc"])
    print("Secrets:", file["secrets"])
    print("Smells:", file["smells"])