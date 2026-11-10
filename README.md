# Fedi Anime Awards

The goal of the project is to provide the [!anime](https://ani.social/c/anime) community with a platform for voting on the best anime of the year.

The process is divided into two phases: the nomination phase and the finals. During the nomination phase, users select, from a pool of approximately 320 of the best anime of the year, the titles most deserving of advancing to the finals across several categories. Each user may select up to 5 entries per category.

This is followed by the final round of voting, in which a single winner is chosen for each category.

Participation requires users to verify their identity using a threadiverse account (Lemmy/Piefed/Mbin).

## Installation

```bash
git clone https://github.com/pkorba/fedi-anime-awards.git
cd fedi-anime-awards
```

Then change the contents of `.env.example` file according to the following configuration section, and rename the file to `.env`

```bash
# Build and run
docker compose up -d --build
```

## How to run once installed

```bash
# Run
docker compose up -d

# Shut down
docker compose down
```

## Configuration

Make sure to replace every `{{ variable }}` in `.env` and `Caddyfile` before proceeding with the setup. 

The `.env` file contains following environment variables that need to be set.

|ENV_VAR|type|description|
|----------------------------------|-------------|-----------|
|`DJANGO_SUPERUSER_USERNAME`       |`string`     |During the first run the app uses this var to create superuser (username).             |
|`DJANGO_SUPERUSER_PASSWORD`       |`string`     |During the first run the app uses this var to create superuser (password).<br/>Make sure it's long and complex. The admin panel is exposed to the internet.             |
|`DJANGO_SECRET_KEY`       |`string`     |This value is the key to securing signed data. Make sure it's long and complex.            |
|`DEBUG`       |`bool`     |`True` to enable debug mode. Set to `False` for production environment.            |
|`ALLOWED_HOSTS`       |`string`     |A list of strings representing the host/domain names that this Django site can serve. This is a security measure to prevent HTTP Host header attacks, which are possible even under many seemingly-safe web server configurations             |
|`CSRF_TRUSTED_ORIGINS`       |`string`     |A list of trusted origins for unsafe requests (e.g. POST).             |
|`SQLITE_PATH`       |`string`     |Database path             |
|`LEMMY_INSTANCE`       |`string`     |Instance of the Lemmy bot account that is used to send private messages to users of the website.             |
|`LEMMY_USERNAME`       |`string`     |Username (without `@instance.tld` part) of the Lemmy bot account that is used to send private messages to users of the website.             |
|`LEMMY_PASSWORD`       |`string`     |Password of the Lemmy bot account that is used to send private messages to users of the website.             |
|`FEDI_ANIME_AWARDS_URL`       |`string`     |The address of a website that will be attached to private messages sent to Threadiverse users.             |
|`CONTACT_URL`       |`string`     |Administrator's contact link (visible in ToS and Privacy Policy), e.g. link to a Lemmy profile.             |
|`CONTACT_USERNAME`       |`string`     |Administrator's contact username (visible in ToS and Privacy Policy). This is what `CONTACT_URL` will look to the users.             |
|`SECURE_SSL_REDIRECT`       |`bool`     |If `True`, redirects all non-HTTPS requests to HTTPS.             |
|`SESSION_COOKIE_SECURE`       |`bool`     |Whether to use a secure cookie for the session cookie. If this is set to `True`, the cookie will be marked as “secure”, which means browsers may ensure that the cookie is only sent under an HTTPS connection.             |
|`CSRF_COOKIE_SECURE`       |`bool`     |Whether to use a secure cookie for the CSRF cookie. If this is set to `True`, the cookie will be marked as “secure”, which means browsers may ensure that the cookie is only sent with an HTTPS connection.             |

Changing the `SQLITE_PATH` requires correcting `compose.yaml` and `Dockerfile` to reflect those changes.

In `Caddyfile` replace `{{ website_main_host }}` with your website's domain name (e.g. `example.com`)

## Admin workflow

The functionality of the admin panel is currently quite limited and assumes a certain number of best practices. Below, I explain the database structure and list the steps an administrator should take after configuring the application to conduct voting.

### Admin site

The below table describes available models. More detailed description of some of them are further down.

|model|description|
|-----------------------|-----------|
|Users     |Contains data about user accounts|
|Categories     |Contains the list of categories subject to voting. It's very important to not change any of the categories. There are parts of code that depend on this structure being the way it is. Currently, adding new categories or changing their names is impossible without introducing changes in code.           |
|Category Shows     |It represents a relation between Category and Show      |
|Characters     |Contains data about characters           |
|Import states     |Always holds only a single import state of the last executed import            |
|Music     |Contains data about music performances         |
|Nomination choices     |Contains user votes in nominations phase           |
|Nomination sets     |Contains user votes in final phase           |
|People     |Contains data about voice performances           |
|Shows     |Contains data about all nominated shows           |
|Voting configs     |Contains the configuration data that determines some of the functionality of the website           |
|Task Results     |Contains detailed data about task performed in the background (currently just the imports)           |

### Initial data explained

Initially, the database contains only predefined information regarding `Categories`, and a default configuration.

The `Categories` must not be altered, as doing so will disrupt the application's functionality.

The configuration consists of three values: `current year`, `finals vote`, and `voting enabled`.

`current year` – determines which year is displayed in various parts of the website (e.g., in titles) and serves as the reference date for calculating the age of user accounts registering on the platform.
The application assumes that the voting takes place in the year following the year for which the voting is held. For instance, if the voting is for the year 2025, only users whose Fediverse accounts were created before January 1, 2026, will be permitted to participate. If an account's age cannot be determined, the user is not granted voting access (registration of their account will fail). The default value initially set here (1000) effectively prevents users from registering accounts. No manual adjustment of this value is required, as `current year` is updated later during the data import process from AniList.

`finals vote` – this value determines the application's current operating mode. `False` indicates that the process is in the nomination phase, while `True` indicates the finals phase. More on this later.

`voting enabled` – this controls whether users are permitted to cast votes. Upon the initial launch of the application, voting is disabled (`voting enabled = False`), allowing for preliminary administrative tasks to be completed. Voting can be enabled or disabled at any time by modifying this value. More on this later.

### Polls admin page layout

The first step for an administrator is to navigate to the Polls application admin page by clicking on the `POLLS` table header (`/admin/polls/`). At the top of this page, you will find the status of the most recent import and a `SHOW RESULTS` link to a page with voting results. Below this, there are controls for importing data from AniList and AnimeThemes, as well as a `Switch to finals` button to toggle the application's operating mode – switching from the nomination phase to the final voting phase.

### Voting preparations

Begin by importing data from AniList: select the year for which you are organizing the vote from the dropdown menu, then click the `Populate the database` button. This process runs as a background task and takes approximately 5-10 minutes. There is no automated notification system to alert you when the task is complete; you must refresh the page to check its status, which is displayed in the `Data import status` section on the same page. It is crucial to perform this import only once, on an empty database – this function does not currently handle data collisions, and attempting to import the same show twice will result in an error. To prevent running it more than once, the button will cease to be visible when there are any entries in Shows.

The AniList data import process works as follows:
- For each season, the system retrieves data for the 80 top-rated shows (based on average score), excluding hentai.
- For each show, it fetches data for the 30 most popular characters (based on the number of "favorites") and all associated songs from AnimeThemes.
- For each character, it retrieves information about their Japanese and English voice actors.
- During the import, the year you selected is automatically saved to the `current year` column in the `Voting configs`. From this point on, users can register, though the voting functionality will remain locked for them.

Importing from AniList automatically assigns a show to a category based on the genres it has on AniList.
|AniList genre| Category in the app|
|-------------|--------------------|
|Action| Action|
|Adventure| Fantasy/Adventure|
|Comedy| Comedy|
|Drama| Drama|
|Fantasy| Fantasy/Adventure|
|Mystery| Drama|
|Psychological| Drama|
|Romance| Romance|
|Sci-Fi| Fantasy/Adventure|
|Slice of Life| Slice of Life|

Additionally, series are added to "Anime of the Year" and "Animation" categories, movies to "Movie of the Year", and every show to "Soundtrack" (it is easier to manually remove excess entries later than to add everything to an empty category).

If you wish to remove an item from the database, you should start by deleting the show itself; deleting a show automatically removes all associated data, such as characters, voice performance (People), and musical sequence (Music), so it saves you a lot of work.

After a successful import, certain shows that have been imported from AniList should be completely removed from the database:
- series that begin in a given year but continue into the next (e.g., a series consisting of two consecutive cours that starts in the autumn and continues through the winter)
- chibi-shorts
- films that have premiered but are not globally available
- compilation films ???

The database may still have gaps. Because of how the query to AniList is structured, a series that began in the previous year but continued into the year for which the voting is being organized will not be imported automatically. Such series must be added manually.
To do this, use the `Add anime` button. Enter the AniList ID of the missing entry into the input field, and click that button. All associated information – characters, voice performances, and music performances – will then be imported.

If you do not wish to remove an entire show, but rather just remove it from a specific category, locate the relevant relationship in the `Category Show` model and delete it. Similarly, if you wish to add a show to a category, create a new entry in `Category Show` and assign the appropriate category and show to it.

Next, in the `Music` section, look for entries that lack a value in the `URL` column (you can change the sort order by clicking on the column header). "Insert songs" usually do not have an associated video on AnimeThemes, so you will need to manually add links from YouTube or another platform that allows public access to the song.

That covers all the necessary preparations for the voting process. Once this is done, you can enable voting by changing the `voting enabled` value in the `Voting configs`.

From this point on, users can cast their votes during the nomination phase.

### Voting process (nominations)

Throughout the voting period, you can monitor its progress by clicking the `SHOW RESULTS` link. The results are always up-to-date, as they are recalculated every time an administrator opens that page.

Should any issues arise, you can suspend the voting process at any time by changing the `voting enabled` value in `Voting configs`.

**If you encounter a problematic user, do not delete their account!**
While deleting the account would remove their votes, it would also allow the user to re-register using the same account name.
Instead, mark such a user as "inactive". This prevents them from re-registering or using their existing account. Their votes remain in the database but are excluded from the results' calculation.

It is possible that, during the finals, you might need to ban a user who participated in the nomination phase – a user whose votes influenced the already finalized nomination results. Since results are calculated in real-time, removing such a user would alter the nomination outcomes. The simplest solution is to save the nomination results to a file once the nomination phase concludes, and then use that saved data whenever necessary (which should happen anyway, as you usually publish the nomination results before starting the finals).

### Voting preparations (finals)

To transition from the nomination phase to the final phase, use the `Switch to Finals` button.
This triggers the following changes:
- Voting is suspended (`voting enabled` is set to `False` in the `Voting configs`).
- The voting system switches to "finals" mode (`finals vote` is set to `True` in the `Voting configs`).
- The application aggregates the results and identifies the 6 entries with the highest number of votes in each category. Each of these entries is assigned a `finalist` flag in the database (characters, people, music, and within the `Category Shows` section for shows).
- If there is a tie for the sixth position in a given category, more than 6 nominees may advance to the finals. If you prefer to limit the finals to exactly 6 entries despite a tie, you can manually disable the `finalist` flag for specific nominees.

Before re-enabling voting, you must manually download images for the finalists in the "Characters," "Musical sequence," and "Voice performance" categories and attach them to the corresponding database models. For the "Voice performance" category (People), you should add illustrations to the characters (in the "Characters" section) that are associated with a specific voice performance. This is because the voting is held for a performance in a particular role, rather than for the actor themselves, so in that section we display character pictures instead photos of actors. The need to manually download images for these categories arises because the way the lists for these categories are displayed changes during the finals, becoming consistent with the layout used for other categories. Furthermore, the images for these entries were not retrieved during the data import from AniList (due to the large number of items making it impractical).

Even when voting is disabled, an administrator can still view the current state of the categories. Disabling voting only affects the accounts of regular users.

After manually adding images, you can restart the voting process by changing the `voting enabled` value to `True` in the `Voting configs`.

To permanently end the voting, change the `voting enabled` setting again and copy the results from the `SHOW RESULTS` section.
