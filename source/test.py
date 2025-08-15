from openai import OpenAI
from source.config.settings import settings

def main() -> None:
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a concise assistant."},
            {"role": "user", "content": "Say hello in one short sentence."},
        ],
        temperature=0.2,
    )
    print(resp.choices[0].message.content)

if __name__ == "__main__":
    main()
