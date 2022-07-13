#[macro_use] extern crate rocket;
use rocket::form::Form;
use rocket_dyn_templates::{Template, context};



#[derive(FromForm)]
struct Container<'r> {
    r#reponame: &'r str,
}

#[post("/new", data = "<container>")]
fn new(container: Form<Container<'_>>) -> &'static str {
    "TODO: Return repo url and/or web/container address"
}

#[get("/")]
fn index() -> Template {
    Template::render("index", context! { name: "ok" })
}

#[launch]
fn rocket() -> _{
    rocket::build()
        .mount("/", routes![index, new])
        .attach(Template::fairing())
}
