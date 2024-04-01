const express = require("express")
const app = express()
const port = 5000

const mysql = require('mysql2')

DB_USER = process.env.DB_USER;
DB_PASSWORD = process.env.DB_PASSWORD;
DB_HOST = process.env.DB_HOST;
DB_PORT = process.env.DB_PORT;
DB_NAME = process.env.DB_NAME;

app.get("/", (req, res) => {
  res.send("Hello World!<br />Check /health to verify database connection is also OK")
})

app.get("/health", (req, res) => {
  // Create connection to database
  // Get database settings from environment
  let health = "BAD"
  const connection = mysql.createConnection({
    host: DB_HOST,
    port: DB_PORT,
    user: DB_USER,
    database: DB_NAME,
    password: DB_PASSWORD,
  });

	connection.query(
		'SELECT NOW() AS now',
		function (err, results, fields) {
			if (err) {
        console.error(err)
				res.send(health)
			} else {
				console.log(results) // results contains rows returned by server
				console.log(fields) // fields contains extra meta data about results, if available
				health = "OK"
				res.send(health)	
			}
		}
	);
})

app.listen(port, () => {
  console.log(`Example app listening on port ${port}`)
})
