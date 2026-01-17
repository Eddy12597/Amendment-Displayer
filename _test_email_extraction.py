import main

# print("Testing: AI extraction")
# for i in range(1,13):
#     print(f"[{i}/12]")
#     filename = f"./email-tests/test-{i}-{"ok" if i <= 4 else ("tricky" if i <= 10 else ("fail"))}.txt"
#     with open(filename) as f:
#         content = f.read()
#     amd = main.Amendment.from_email(main.Email("test@example.com", "Model UN Amendment", content))
#     if amd is None:
#         print(f"Result is None for test case {i}")

print("Now testing: Non-AI extraction")
for i in range(1,13):
    print(f"[{i}/12]")
    filename = f"./email-tests/test-{i}-{"ok" if i <= 4 else ("tricky" if i <= 10 else ("fail"))}.txt"
    with open(filename) as f:
        content = f.read()
    amd = main.Amendment.from_email(main.Email("test@example.com", "Model UN Amendment", content), use_ai_if_possible=False)
    if amd is None:
        print(f"Result is None for test case {i}")