export const VIEWS = [
    {
        id: "files",
        label: "FILES",
        hint: "Sources and documents",
        hideOnMobile: true,
    },
    {
        id: "map",
        label: "MAP",
        hint: "Entities and connections",
        hideOnMobile: false,
    },
    {
        id: "index",
        label: "INDEX",
        hint: "Data by source",
        hideOnMobile: false,
    },
    {
        id: "about",
        label: "ABOUT",
        hint: "Overview of the search",
        hideOnMobile: false,
    },
    {
        id: "submit",
        label: "SUBMIT",
        hint: "Follow-up leads",
        hideOnMobile: false,
    },
] as const;

export type ViewId = (typeof VIEWS)[number]["id"];
