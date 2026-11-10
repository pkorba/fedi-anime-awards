GET_SHOWS = """
query (
    $page: Int = 1
    $perPage: Int = 50
    $season: MediaSeason!
    $year: Int!
) {
    Page(page: $page, perPage: $perPage) {
        pageInfo {
            currentPage
            hasNextPage
            total
        }

        media(
            type: ANIME
            season: $season
            seasonYear: $year
            format_not_in: [TV_SHORT, MUSIC]
            genre_not_in: ["Hentai"]
            popularity_greater: 500
            sort: [SCORE_DESC]
        ) {
            id
            idMal

            title {
                romaji
                english
            }

            format
            genres
            
            coverImage {
                large
            }
        }
    }
}
"""

GET_SHOW = """
query (
    $page: Int = 1
    $perPage: Int = 1
    $id: Int!
) {
    Page(page: $page, perPage: $perPage) {
        pageInfo {
            currentPage
            hasNextPage
            total
        }

        media(
            id: $id
        ) {
            id
            idMal

            title {
                romaji
                english
            }

            format
            genres
            
            coverImage {
                large
            }
        }
    }
}
"""

GET_CHARACTERS = """
query (
    $ids: [Int]
    $page: Int = 1
    $perPage: Int = 10
    $charactersPage: Int = 1
    $language: StaffLanguage!
) {
    Page(page: $page, perPage: $perPage) {
        pageInfo {
            currentPage
            hasNextPage
            total
        }

        media(id_in: $ids, type: ANIME) {
            id
            characters(
                page: $charactersPage,
                perPage: 30,
                sort: FAVOURITES_DESC
            ) {
                pageInfo {
                    currentPage
                    hasNextPage
                }

                edges {
                    node {
                        id
                        name {
                            full
                        }
                        image {
                            large
                        }
                    }
                    voiceActors(language: $language) {
                        id
                        name {
                            full
                        }
                        languageV2
                    }
                }
            }
        }
    }
}
"""

GET_SONGS = """
query ($id: [Int!]) {
    findAnimeByExternalSite(site: ANILIST, id: $id) {
        title {
            romaji
            english
        }
        resources(site: ANILIST) {
            nodes {
                externalId
            }
        }
        animethemes {
            animethemeentries {
                videos {
                    nodes {
                        link
                    }
                }
            }
            song {
                title {
                    romaji
                }
            }
            type
            sequence
        }
    }
}
"""
