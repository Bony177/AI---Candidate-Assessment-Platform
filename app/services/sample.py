class User:

    def login(self, username):
        if username:
            return True

        return False

    def logout(self):
        print("logout")


def calculate(a, b):
    for i in range(a):
        print(i)

    return b