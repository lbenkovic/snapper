# Snapper Social Media App

-   Nositelj: doc. dr. sc. Nikola Tanković
-   Asistent: mag. inf. Luka Blašković

---

-   Student: Luka Benković

## Studijski smjer

```
Studij: Diplomski online studij informatika
```

## Kolegij

```
Kolegij: Raspodijeljeni sustavi
Akademska godina: 2024./2025.
```

## Linkovi

-   Link na video: [YouTube Link](https://youtu.be/vHVYRqWfEEA)

-   Link na dokumentaciju: [Snapper.pdf](https://github.com/user-attachments/files/22297602/luka-benkovic.pdf)


## Opis projekta

Social Media App koja je kombinacija Twitter-a (X-a) i Snapchata, gdje je ideja da se svaka objava/poruka briše nakon nekog vremena. Korisnici mogu odabrati koje objave žele da ostanu spremljene duže vremena (pinane), pratiti ostale korisnike i komunicirati s ostalim korisnicima. Koristi se DynamoDB, FastAPI, WS Websocket i AWS S3.

## Tehnologije

-   **Backend**: Python (FastAPI)
-   **Baza podataka**: AWS DynamoDB
-   **Pohrana datoteka**: AWS S3
-   **WebSocket**: FastAPI WebSocket
-   **Autentifikacija**: JWT
-   **Kontejnerizacija**: Docker & Docker Compose

## Struktura sustava

Aplikacija je podijeljena u pet servisa:

-   **Auth Service** – registracija, prijava i verifikacija korisnika
-   **Message Service** - pohrana poruka, dohvat razgovora
-   **Post Service** - CRUD operacije nad objavama, like, comment, pin na objavama
-   **User Service** – upravljanje korisnicima i korisničkim podacima, pretraživanje korisnika, follow/unfollow funkcije
-   **WS Messaging Service** - upravljanje WebSocket-om
